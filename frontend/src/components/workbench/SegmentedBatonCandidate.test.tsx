import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { SegmentedBatonCandidate, SegmentedResponsePlayer } from "./SegmentedBatonCandidate";
import type { SegmentedBatonRenderResponse } from "../../types/teachintent";

const result: SegmentedBatonRenderResponse = {
  session_id: "session-1", status: "success", renderer: "batonvoice_segmented", run_id: "run-1",
  speech_speed: 0.85, manifest_metadata: {},
  segments: [4, 2, 1, 3].map((order) => ({
    segment_id: `seg_0${order}`, order, status: "success", audio_url: `/segment-${order}.wav`,
    duration_seconds: 1, text_sha256: "hash", text_char_count: 10, mapped: {},
    mapping_diagnostics: {}, executor_diagnostics: {}, failure_reasons: [],
  })),
};

describe("segmented playback", () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("preloads in order, plays from first, advances on ended, and finishes without looping", async () => {
    const user = userEvent.setup();
    const { container } = render(<SegmentedResponsePlayer result={result} />);
    const audios = [...container.querySelectorAll("audio")];
    expect(audios.map((a) => a.getAttribute("src"))).toEqual([1, 2, 3, 4].map((i) => `/segment-${i}.wav`));
    expect(audios.every((a) => a.preload === "auto")).toBe(true);
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
    await user.click(screen.getByText("Play full segmented response"));
    expect(vi.mocked(HTMLMediaElement.prototype.play).mock.instances).toEqual([audios[0]]);
    for (let i = 0; i < 3; i++) {
      fireEvent.ended(audios[i]);
      expect(vi.mocked(HTMLMediaElement.prototype.play).mock.instances.at(-1)).toBe(audios[i + 1]);
    }
    fireEvent.ended(audios[3]);
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(4);
    expect(screen.getByText("Stop")).toBeDisabled();
    expect(screen.getByText("Play full segmented response")).toBeEnabled();
    fireEvent.ended(audios[3]);
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(4);
  });

  it("stop prevents advancement and restart begins at segment one", async () => {
    const user = userEvent.setup();
    const { container, unmount } = render(<SegmentedResponsePlayer result={result} />);
    const audios = [...container.querySelectorAll("audio")];
    await user.click(screen.getByText("Play full segmented response"));
    fireEvent.ended(audios[0]);
    await user.click(screen.getByText("Stop"));
    fireEvent.ended(audios[1]);
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(2);
    await user.click(screen.getByText("Restart from first segment"));
    expect(vi.mocked(HTMLMediaElement.prototype.play).mock.instances.at(-1)).toBe(audios[0]);
    unmount();
    expect(audios.every((a) => a.currentTime === 0)).toBe(true);
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
  });

  it.each(["partial_failure", "failed", "interrupted"] as const)("does not play an incomplete %s response", (status) => {
    render(<SegmentedResponsePlayer result={{ ...result, status }} />);
    expect(screen.getByText("Play full segmented response")).toBeDisabled();
    expect(screen.getByText("Restart from first segment")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(status);
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
  });

  it("stops on play rejection and on audio loading failure without skipping", async () => {
    const user = userEvent.setup();
    vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new Error("blocked"));
    const { container } = render(<SegmentedResponsePlayer result={result} />);
    await user.click(screen.getByText("Play full segmented response"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Playback could not start");
    expect(screen.getByText("Stop")).toBeDisabled();
    await user.click(screen.getByText("Play full segmented response"));
    fireEvent.error(container.querySelectorAll("audio")[1]);
    expect(screen.getByRole("alert")).toHaveTextContent("without skipping");
    expect(screen.getByText("Stop")).toBeDisabled();
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(2);
  });

  it("ignores a stale rejected play promise after stop and restart", async () => {
    let reject: (reason: Error) => void = () => {};
    vi.mocked(HTMLMediaElement.prototype.play).mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
    const user = userEvent.setup();
    render(<SegmentedResponsePlayer result={result} />);
    await user.click(screen.getByText("Play full segmented response"));
    await user.click(screen.getByText("Stop"));
    await user.click(screen.getByText("Restart from first segment"));
    await act(async () => reject(new Error("old request")));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Stop")).toBeEnabled();
  });

  it("render calls only the candidate API and playback never resynthesizes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<SegmentedBatonCandidate sessionId="session-1" />);
    await user.click(screen.getByText("Render segmented candidate"));
    await screen.findByText("Segmented render complete.");
    await user.click(screen.getByText("Play full segmented response"));
    await user.click(screen.getByText("Restart from first segment"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/render/batonvoice-segmented", expect.objectContaining({
      body: JSON.stringify({ session_id: "session-1" }),
    }));
  });

  it("discards an old session response after unmount", async () => {
    let resolve: (response: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise((done) => { resolve = done; })));
    const user = userEvent.setup();
    const { rerender } = render(<SegmentedBatonCandidate key="old" sessionId="old" />);
    await user.click(screen.getByText("Render segmented candidate"));
    rerender(<SegmentedBatonCandidate key="new" sessionId="new" />);
    await act(async () => resolve(new Response(JSON.stringify(result), { status: 200 })));
    await waitFor(() => expect(screen.queryByText("Play full segmented response")).not.toBeInTheDocument());
    expect(screen.getByText("Render segmented candidate")).toBeEnabled();
  });

  it("stops the old queue when a new render starts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(result), { status: 200 }))
      .mockImplementationOnce(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { container } = render(<SegmentedBatonCandidate sessionId="session-1" />);
    await user.click(screen.getByText("Render segmented candidate"));
    await screen.findByText("Segmented render complete.");
    await user.click(screen.getByText("Play full segmented response"));
    const first = container.querySelector("audio")!;
    vi.mocked(HTMLMediaElement.prototype.pause).mockClear();
    await user.click(screen.getByText("Render segmented candidate"));
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalledTimes(4);
    expect(screen.queryByText("Play full segmented response")).not.toBeInTheDocument();
    fireEvent.ended(first);
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
