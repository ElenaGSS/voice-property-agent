import {
  AnswerItem,
  NextQuestionRequest,
  NextQuestionResponse,
  ReportResponse,
} from "@/types/interview";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, options);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function transcribeAudio(
  file: Blob,
  currentQuestion?: string,
  signal?: AbortSignal,
): Promise<string> {
  const formData = new FormData();
  formData.append("file", file, "answer.webm");
  if (currentQuestion) {
    formData.append("current_question", currentQuestion);
  }
  try {
    const data = await request<{ text: string; raw_text?: string | null }>(
      "/api/transcribe",
      {
        method: "POST",
        body: formData,
        signal,
      },
    );
    return data.text;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("TRANSCRIBE_ABORTED");
    }
    throw error;
  }
}

export async function fetchNextQuestion(
  payload: NextQuestionRequest,
): Promise<NextQuestionResponse> {
  return request<NextQuestionResponse>("/api/next-question", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function generateReport(
  sessionId: string,
  answers: AnswerItem[],
): Promise<ReportResponse> {
  return request<ReportResponse>("/api/generate-report", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      answers,
    }),
  });
}
