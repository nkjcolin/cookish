"""Storage adapters for image jobs. Local SQLite/files are never used on Lambda."""

import json
import os
import sqlite3
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

MAX_ATTEMPTS = 3
TERMINAL = {"completed", "failed"}
Record = dict[str, Any]


class LocalJobStore:
    """Two local processes can share this store; no model runs in the HTTP process."""

    def __init__(self, root: Path):
        self.root = root
        (root / "images").mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs "
                "(job_id TEXT PRIMARY KEY, record TEXT NOT NULL, dispatched INTEGER DEFAULT 0)"
            )

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.root / "jobs.sqlite3", timeout=5)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, record: Record) -> Record:
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO jobs(job_id, record) VALUES (?, ?)",
                (record["job_id"], json.dumps(record)),
            )
            return json.loads(
                db.execute(
                    "SELECT record FROM jobs WHERE job_id = ?", (record["job_id"],)
                ).fetchone()[0]
            )

    def get(self, job_id: str) -> Record | None:
        with self.connection() as db:
            row = db.execute("SELECT record FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_image(self, job_id: str, data: bytes, media_type: str) -> None:
        # Atomic rename avoids partially read images on a repeated submission.
        temporary = self.root / "images" / f"{job_id}.{uuid4()}.tmp"
        temporary.write_bytes(data)
        temporary.replace(self.root / "images" / job_id)

    def read_image(self, job_id: str) -> bytes:
        return (self.root / "images" / job_id).read_bytes()

    def delete_image(self, job_id: str) -> None:
        (self.root / "images" / job_id).unlink(missing_ok=True)

    def enqueue(self, job_id: str) -> None:
        with self.connection() as db:
            db.execute("UPDATE jobs SET dispatched = 1 WHERE job_id = ?", (job_id,))

    def pending(self, now: int) -> list[str]:
        with self.connection() as db:
            rows = db.execute("SELECT record FROM jobs WHERE dispatched = 1").fetchall()
        return [
            record["job_id"]
            for (raw,) in rows
            if (record := json.loads(raw))["status"] not in TERMINAL
            and record["lease_until"] <= now
        ]

    def claim(self, job_id: str, now: int, lease_seconds: int) -> Record | None:
        with self.connection() as db:
            row = db.execute("SELECT record FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return None
            record = json.loads(row[0])
            if (
                record["status"] in TERMINAL
                or record["lease_until"] > now
                or record["attempts"] >= MAX_ATTEMPTS
                or record["work_deadline"] <= now
            ):
                return None
            record.update(
                status="processing",
                attempts=record["attempts"] + 1,
                lease_until=now + lease_seconds,
                lease_token=str(uuid4()),
            )
            db.execute("UPDATE jobs SET record = ? WHERE job_id = ?", (json.dumps(record), job_id))
            return record

    def update(self, job_id: str, changes: Record, lease_token: str | None = None) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT record FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return False
            record = json.loads(row[0])
            if record["status"] in TERMINAL or (
                lease_token is not None and record["lease_token"] != lease_token
            ):
                return False
            record.update(changes)
            db.execute("UPDATE jobs SET record = ? WHERE job_id = ?", (json.dumps(record), job_id))
            return True

    def cleanup(self, now: int) -> None:
        with self.connection() as db:
            for job_id, raw in db.execute("SELECT job_id, record FROM jobs").fetchall():
                if json.loads(raw)["expires_at"] <= now:
                    self.delete_image(job_id)
                    db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))


class AwsJobStore:
    def __init__(self):
        self.bucket = os.environ["AI_JOB_BUCKET"]
        self.queue_url = os.environ["AI_JOB_QUEUE_URL"]
        config = Config(connect_timeout=2, read_timeout=5, retries={"total_max_attempts": 2})
        self.s3 = boto3.client("s3", config=config)
        self.sqs = boto3.client("sqs", config=config)
        self.table = boto3.resource("dynamodb", config=config).Table(os.environ["AI_JOB_TABLE"])

    @staticmethod
    def _conditional(exc: ClientError) -> bool:
        return exc.response["Error"]["Code"] == "ConditionalCheckFailedException"

    def create(self, record: Record) -> Record:
        try:
            self.table.put_item(Item=record, ConditionExpression="attribute_not_exists(job_id)")
            return record
        except ClientError as exc:
            if not self._conditional(exc):
                raise
            existing = self.get(record["job_id"])
            if existing is None:
                raise RuntimeError("Image job disappeared during creation") from None
            return existing

    def get(self, job_id: str) -> Record | None:
        return self.table.get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item")

    def put_image(self, job_id: str, data: bytes, media_type: str) -> None:
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"images/{job_id}",
            Body=data,
            ContentType=media_type,
            ServerSideEncryption="AES256",
        )

    def read_image(self, job_id: str) -> bytes:
        response = self.s3.get_object(Bucket=self.bucket, Key=f"images/{job_id}")
        stream = response["Body"]
        try:
            # Reject oversized storage objects as well as oversized API uploads.
            return stream.read(3 * 1024 * 1024 + 1)
        finally:
            stream.close()

    def delete_image(self, job_id: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=f"images/{job_id}")

    def enqueue(self, job_id: str) -> None:
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=json.dumps({"job_id": job_id}))

    def defer(self, receipt_handle: str, seconds: int) -> None:
        self.sqs.change_message_visibility(
            QueueUrl=self.queue_url, ReceiptHandle=receipt_handle, VisibilityTimeout=seconds
        )

    def claim(self, job_id: str, now: int, lease_seconds: int) -> Record | None:
        try:
            return self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=(
                    "SET #s = :processing, lease_until = :lease, lease_token = :token, "
                    "attempts = attempts + :one"
                ),
                ConditionExpression=(
                    "(#s = :queued OR (#s = :processing AND lease_until <= :now)) "
                    "AND attempts < :max AND work_deadline > :now"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":processing": "processing",
                    ":queued": "queued",
                    ":lease": now + lease_seconds,
                    ":token": str(uuid4()),
                    ":one": 1,
                    ":now": now,
                    ":max": MAX_ATTEMPTS,
                },
                ReturnValues="ALL_NEW",
            )["Attributes"]
        except ClientError as exc:
            if not self._conditional(exc):
                raise
            return None

    def update(self, job_id: str, changes: Record, lease_token: str | None = None) -> bool:
        names = {f"#f{i}": key for i, key in enumerate(changes)}
        values = {f":v{i}": value for i, value in enumerate(changes.values())}
        names["#s"] = "status"
        values.update({":queued": "queued", ":processing": "processing"})
        condition = "(#s = :queued OR #s = :processing)"
        if lease_token is not None:
            condition += " AND lease_token = :token"
            values[":token"] = lease_token
        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET " + ", ".join(f"#f{i} = :v{i}" for i in range(len(changes))),
                ConditionExpression=condition,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
            return True
        except ClientError as exc:
            if not self._conditional(exc):
                raise
            return False


JobStore = LocalJobStore | AwsJobStore


@cache
def get_job_store() -> JobStore:
    backend = os.environ.get("AI_JOB_BACKEND", "local")
    if backend == "aws":
        return AwsJobStore()
    if backend != "local" or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        raise ValueError("Lambda requires AI_JOB_BACKEND=aws and the image job resource settings")
    return LocalJobStore(
        Path(os.environ.get("AI_JOB_LOCAL_DIR", str(Path(__file__).parents[1] / "output" / "jobs")))
    )
