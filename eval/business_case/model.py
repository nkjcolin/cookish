"""Reproducible USD planning model; no network, billing, or measured-usage claims."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = Decimal


def number(value):
    result = D(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("cost inputs must be finite and nonnegative")
    return result


def formatted(value):
    return str(value.quantize(D("0.000001")))


def fixed_costs(assumptions, rates):
    quantity = assumptions["fixed"]
    fields = {
        "database": ("database_hours", "rds_hour"),
        "database_storage": ("database_storage_gb", "rds_storage_gb_month"),
        "secrets": ("secrets", "secret_month"),
        "builds": ("build_minutes", "amplify_build_minute"),
        "frontend_storage": ("frontend_storage_gb", "amplify_storage_gb_month"),
        "dashboards": ("dashboards", "dashboard"),
        "custom_metrics": ("custom_metrics", "custom_metric"),
        "alarm_metrics": ("alarm_metrics", "alarm_metric"),
    }
    return {name: number(quantity[field]) * rates[rate] for name, (field, rate) in fields.items()}


def calculate(assumptions, rates, households, paid_share, workload):
    households, paid_share = number(households), number(paid_share)
    if households < 1 or households != int(households) or paid_share > 1:
        raise ValueError("households must be positive integers and paid share between zero and one")
    c = {key: number(value) for key, value in assumptions["common_usage"].items()}
    w = {key: number(value) for key, value in assumptions["workloads"][workload].items()}
    if c["share_of_active_free_households_new_this_month"] > 1:
        raise ValueError("new free household share cannot exceed one")
    if not c["monthly_active_accounts_per_household"]:
        raise ValueError("active accounts per household must be positive")
    if w["paid_imports"] > c["proposed_paid_import_limit_per_month"]:
        raise ValueError("paid import hypothesis exceeds the proposed limit")
    if c["outer_attempts_per_import"] < 1 or w["model_attempts_per_import"] < 1:
        raise ValueError("attempt multipliers must include the original attempt")
    if c["http_billing_units_per_ai_upload"] < 1:
        raise ValueError("AI uploads need at least one HTTP API billing unit")

    free_imports = (
        c["free_trial_imports_once"] * c["share_of_active_free_households_new_this_month"]
    )
    imports = (1 - paid_share) * free_imports + paid_share * w["paid_imports"]
    ai_invocations = imports * c["outer_attempts_per_import"]
    model_attempts = ai_invocations * w["model_attempts_per_import"]
    api_calls = w["non_ai_api_requests"]
    invocations = api_calls + ai_invocations
    variable = {
        "api_lambda_duration": c["lambda_memory_gb"]
        * rates["lambda_gb_second"]
        * api_calls
        * w["api_seconds"],
        "ai_lambda_duration": c["lambda_memory_gb"]
        * rates["lambda_gb_second"]
        * model_attempts
        * w["ai_seconds_per_model_attempt"],
        "lambda_requests": invocations * rates["lambda_request"],
        "http_api": (api_calls + c["http_billing_units_per_ai_upload"] * ai_invocations)
        * rates["http_api_unit"],
        "model_provider_assumed": model_attempts * w["assumed_model_usd_per_attempt"],
        "frontend_egress": w["frontend_egress_gb"] * rates["amplify_egress_gb"],
        "other_internet_egress": w["other_internet_egress_gb"] * rates["internet_egress_gb"],
        "log_ingestion": w["log_ingestion_and_retention_gb"] * rates["log_ingest_gb"],
        "log_storage": w["log_ingestion_and_retention_gb"] * rates["log_storage_gb_month"],
        "secret_api_calls": invocations
        * c["secret_reads_per_lambda_invocation"]
        * rates["secret_api_call"],
        "cognito_gross": c["monthly_active_accounts_per_household"] * rates["cognito_mau"],
    }
    fixed = sum(fixed_costs(assumptions, rates).values())
    cost = fixed + households * sum(variable.values())
    paid = households * paid_share
    accounts = households * c["monthly_active_accounts_per_household"]
    revenue = paid * number(assumptions["monthly_price_per_paying_household"])
    auth_allowance = min(accounts, c["cognito_allowance_for_separate_sensitivity"])
    return {
        "active_households": int(households),
        "paid_share": str(paid_share),
        "workload": workload,
        "paying_households": str(paid),
        "active_accounts_assumed": str(accounts),
        "imports_per_active_household": str(imports),
        "model_attempts_per_active_household": str(model_attempts),
        "monthly_variable_components_usd": {
            name: formatted(value * households) for name, value in variable.items()
        },
        "monthly_total_usd": formatted(cost),
        "per_active_household_usd": formatted(cost / households),
        "per_active_account_usd": formatted(cost / accounts),
        "allocated_per_paying_household_usd": formatted(cost / paid) if paid else None,
        "subscription_revenue_usd": formatted(revenue),
        "revenue_less_infrastructure_only_usd": formatted(revenue - cost),
        "separate_cognito_allowance_sensitivity": {
            "assumption": "Fully available 10000 MAU allowance; no other allowances deducted",
            "monthly_total_usd": formatted(cost - auth_allowance * rates["cognito_mau"]),
        },
    }


def digest(path):
    # Match Git's text content across Windows CRLF and Linux LF checkouts.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def build_report(assumptions_path, rates_path):
    assumptions = json.loads(assumptions_path.read_text(encoding="utf-8"))
    snapshot = json.loads(rates_path.read_text(encoding="utf-8"))
    rates = {key: number(value["usd"]) for key, value in snapshot["rates"].items()}
    if (
        assumptions["currency"] != "USD"
        or assumptions["region"] != "ap-southeast-1"
        or snapshot["currency"] != "USD"
        or snapshot["primary_region"] != "ap-southeast-1"
    ):
        raise ValueError("this rate snapshot covers Singapore AWS charges in USD")
    if any(
        assumptions["lambda_architecture"] != snapshot["rates"][key]["architecture"]
        for key in ("lambda_gb_second", "lambda_request")
    ):
        raise ValueError("Lambda architecture must match the selected duration and request rates")
    rows = [
        calculate(assumptions, rates, count, assumptions["main_paid_share"], workload)
        for count in assumptions["active_households"]
        for workload in assumptions["workloads"]
    ]
    sensitivity = [
        calculate(assumptions, rates, count, share, "base")
        for count in assumptions["active_households"]
        for share in assumptions["paid_share_sensitivity"]
    ]
    fixed = fixed_costs(assumptions, rates)
    return {
        "version": 1,
        "as_of": assumptions["as_of"],
        "currency": "USD",
        "lambda_architecture": assumptions["lambda_architecture"],
        "status": (
            "Planning estimate: published rates plus assumed usage; "
            "not measured or a capacity claim"
        ),
        "cost_basis": "Gross list price; no credits, discounts, tax or free allowances deducted",
        "excluded": [
            "payment and app-store fees",
            "engineering and support labor",
            "recipe review",
            "customer acquisition",
            "refunds",
            "domain",
            "verification email",
            "extra backup/snapshot storage",
            "cross-AZ traffic",
            "log-query and metric API calls",
            "excess RDS CPU credits",
            "optional security services",
            "capacity/availability upgrades",
        ],
        "input_sha256": {
            assumptions_path.name: digest(assumptions_path),
            rates_path.name: digest(rates_path),
            "model.py": digest(Path(__file__)),
        },
        "input_hash_method": "SHA-256 of UTF-8 text after normalizing line endings to LF",
        "fixed_monthly_components_usd": {name: formatted(value) for name, value in fixed.items()},
        "fixed_monthly_total_usd": formatted(sum(fixed.values())),
        "main_scenarios": rows,
        "paid_share_sensitivity": sensitivity,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assumptions", type=Path, default=HERE / "assumptions.json")
    parser.add_argument("--rates", type=Path, default=HERE / "aws-rates.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.assumptions, args.rates)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("USD gross planning estimates; assumed usage; no capacity or profit claim")
    print("Households | Workload | Total/month | Per active HH | Per paying HH")
    for row in report["main_scenarios"]:
        print(
            f"{row['active_households']:>10} | {row['workload']:>8} | "
            f"{row['monthly_total_usd']:>11} | {row['per_active_household_usd']:>13} | "
            f"{row['allocated_per_paying_household_usd']}"
        )


if __name__ == "__main__":
    main()
