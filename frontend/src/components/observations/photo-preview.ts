// Preview URLs for photos that are still waiting to be uploaded.
//
// Rendering a camera JPEG through its own object URL makes the renderer decode it at
// full resolution (a 4000×3000 photo costs about 48 MB of bitmaps). A queue of them
// exhausts the image cache, so scrolling stalls on decode and paints blank frames.
// Previews are therefore drawn from one decoded bitmap and released with
// `releasePhotoPreview`.
const PREVIEW_MAX_EDGE = 1280;
const THUMB_MAX_EDGE = 160;

export interface PhotoPreviewUrls {
  previewUrl: string;
  thumbUrl: string;
}

async function decode(file: File): Promise<ImageBitmap | null> {
  try {
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return null;
  }
}

function paint(bitmap: ImageBitmap, maxEdge: number, quality: number): Promise<string> {
  const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("无法创建预览画布");
  context.drawImage(bitmap, 0, 0, width, height);
  return new Promise<string>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(URL.createObjectURL(blob)) : reject(new Error("无法生成预览图"))),
      "image/jpeg",
      quality,
    );
  });
}

async function draw(file: File, maxEdge: number, quality: number): Promise<string> {
  const bitmap = await decode(file);
  // Undecodable file: keep the old behaviour so the reader still sees what was picked.
  if (!bitmap) return URL.createObjectURL(file);
  try {
    return await paint(bitmap, maxEdge, quality);
  } catch {
    return URL.createObjectURL(file);
  } finally {
    bitmap.close();
  }
}

export async function photoPreviewUrls(file: File): Promise<PhotoPreviewUrls> {
  const bitmap = await decode(file);
  if (!bitmap) {
    const url = URL.createObjectURL(file);
    return { previewUrl: url, thumbUrl: url };
  }
  const created: string[] = [];
  try {
    const previewUrl = await paint(bitmap, PREVIEW_MAX_EDGE, 0.85);
    created.push(previewUrl);
    const thumbUrl = await paint(bitmap, THUMB_MAX_EDGE, 0.8);
    created.push(thumbUrl);
    return { previewUrl, thumbUrl };
  } catch {
    created.forEach((url) => URL.revokeObjectURL(url));
    const url = URL.createObjectURL(file);
    return { previewUrl: url, thumbUrl: url };
  } finally {
    bitmap.close();
  }
}

/** Single downscaled copy, for forms that show one photo at a time. */
export function photoPreviewUrl(file: File): Promise<string> {
  return draw(file, PREVIEW_MAX_EDGE, 0.85);
}

/** Small queue thumbnail. */
export function photoThumbUrl(file: File): Promise<string> {
  return draw(file, THUMB_MAX_EDGE, 0.8);
}

export function releasePhotoPreview(urls: Partial<PhotoPreviewUrls>): void {
  const released = new Set<string>();
  for (const url of [urls.previewUrl, urls.thumbUrl]) {
    if (!url || released.has(url)) continue;
    released.add(url);
    URL.revokeObjectURL(url);
  }
}

export function releasePreviewUrl(url: string): void {
  if (url) URL.revokeObjectURL(url);
}
