/**
 * Longest edge of a photo sent for recognition. Role 4's latency test decides the final
 * value (SPEC A4); the whole request must stay under Lambda's 6 MB limit.
 */
export const MAX_IMAGE_EDGE = 1500;
const JPEG_QUALITY = 0.8;

/** Downscales a photo in the browser and returns it as base64 JPEG, without the data: prefix. */
export async function compressImage(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas.toDataURL("image/jpeg", JPEG_QUALITY).split(",")[1]!;
}
