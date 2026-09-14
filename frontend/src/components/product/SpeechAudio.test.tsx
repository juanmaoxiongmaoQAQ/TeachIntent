import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SpeechAudio } from "./SpeechAudio";
import { json } from "../../test/fixtures";

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it("keeps explicit single-pass execution and stops its audio when leaving", async () => {
  vi.mocked(fetch).mockResolvedValue(
    json({
      renderer: "batonvoice",
      session_id: "s",
      status: "success",
      audio_url: "/mock.wav",
    }),
  );
  const { unmount } = render(
    <SpeechAudio sessionId="s" mode="single" onDetails={vi.fn()} />,
  );
  expect(fetch).not.toHaveBeenCalled();
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "生成语音" }));
  const audio = await screen.findByLabelText("试听生成的语音");
  expect(audio).not.toHaveAttribute("autoplay");
  expect(fetch).toHaveBeenCalledWith(
    "/api/render/batonvoice",
    expect.objectContaining({ body: JSON.stringify({ session_id: "s" }) }),
  );
  unmount();
  expect(vi.mocked(HTMLMediaElement.prototype.pause).mock.instances).toContain(
    audio,
  );
});
it("rejects mismatched sessions without playback, retry or fallback", async () => {
  const details = vi.fn();
  vi.mocked(fetch).mockResolvedValue(
    json({
      renderer: "batonvoice",
      session_id: "old",
      status: "success",
      audio_url: "/old.wav",
    }),
  );
  const { container } = render(
    <SpeechAudio sessionId="new" mode="single" onDetails={details} />,
  );
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "生成语音" }));
  expect(
    await screen.findByText("语音生成失败，请检查服务配置后重试。"),
  ).toBeVisible();
  expect(container.querySelector("audio")).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(details).toHaveBeenCalledWith({ error: "语音返回的会话不匹配。" });
});
