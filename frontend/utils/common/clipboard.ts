/**
 * Clipboard helper.
 *
 * Why execCommand-only: `navigator.clipboard` requires a secure context
 * (HTTPS or localhost). Deployment is HTTP, so modern path is never used in
 * prod — keeping the branch would leave dev/prod on different code paths and
 * risk "works in dev, breaks in prod" bugs. `execCommand('copy')` works
 * universally with no removal plan in any major browser.
 */
export async function copyToClipboard(text: string): Promise<void> {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "0";
  ta.style.left = "0";
  ta.style.opacity = "0";
  ta.style.pointerEvents = "none";
  document.body.appendChild(ta);
  ta.select();
  ta.setSelectionRange(0, ta.value.length);
  try {
    (document as { execCommand: (cmd: string) => boolean }).execCommand("copy");
  } finally {
    document.body.removeChild(ta);
  }
}
