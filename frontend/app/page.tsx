"use client";

import { useMemo, useRef, useState } from "react";
import { LeadBadge } from "@/components/LeadBadge";
import {
  fetchNextQuestion,
  generateReport,
  transcribeAudio,
} from "@/services/api";
import { AnswerItem, ReportResponse } from "@/types/interview";

const TOTAL_QUESTIONS = 12;
const FIRST_QUESTION = "Как вас зовут?";
const ROUND_NAMES: Record<number, string> = {
  1: "Контактные данные",
  2: "Объект",
  3: "Причина обращения",
  4: "Ожидания",
};

function createSessionId() {
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function Home() {
  const [screen, setScreen] = useState<"landing" | "interview" | "report">(
    "landing",
  );
  const [sessionId, setSessionId] = useState(createSessionId);
  const [currentRound, setCurrentRound] = useState(1);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(FIRST_QUESTION);
  const [answers, setAnswers] = useState<AnswerItem[]>([]);
  const [transcript, setTranscript] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isGeneratingQuestion, setIsGeneratingQuestion] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [isInterviewComplete, setIsInterviewComplete] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<ReportResponse | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const progressLabel = useMemo(
    () => `${answers.length + (isInterviewComplete ? 0 : 1)} / ${TOTAL_QUESTIONS}`,
    [answers.length, isInterviewComplete],
  );

  async function startInterview() {
    resetState();
    setScreen("interview");
  }

  function resetState() {
    setSessionId(createSessionId());
    setCurrentRound(1);
    setCurrentQuestionIndex(0);
    setCurrentQuestion(FIRST_QUESTION);
    setAnswers([]);
    setTranscript("");
    setError("");
    setReport(null);
    setIsInterviewComplete(false);
  }

  async function startRecording() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        streamRef.current?.getTracks().forEach((track) => track.stop());
        await handleTranscription(audioBlob);
      };

      recorder.start();
      setIsRecording(true);
    } catch (recordingError) {
      setError(
        "Не удалось получить доступ к микрофону. Проверьте разрешения браузера.",
      );
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setIsRecording(false);
  }

  async function handleTranscription(audioBlob: Blob) {
    setIsTranscribing(true);
    setError("");
    try {
      const text = await transcribeAudio(audioBlob);
      setTranscript(text);
    } catch (transcriptionError) {
      setError(
        "Backend не смог обработать аудио. Можно включить WHISPER_MOCK_MODE=true или ввести ответ вручную.",
      );
    } finally {
      setIsTranscribing(false);
    }
  }

  async function saveAnswerAndContinue() {
    if (!transcript.trim()) {
      setError("Добавьте ответ: запишите аудио или введите текст вручную.");
      return;
    }

    const updatedAnswers = [
      ...answers,
      {
        round: currentRound,
        question: currentQuestion,
        answer: transcript.trim(),
      },
    ];
    setAnswers(updatedAnswers);
    setTranscript("");
    setError("");

    if (updatedAnswers.length >= TOTAL_QUESTIONS) {
      setIsInterviewComplete(true);
      return;
    }

    setIsGeneratingQuestion(true);
    try {
      const next = await fetchNextQuestion({
        session_id: sessionId,
        current_round: currentRound,
        current_question_index: currentQuestionIndex,
        answers: updatedAnswers,
      });

      setCurrentRound(next.round);
      setCurrentQuestionIndex(next.question_index);
      setCurrentQuestion(next.question);
      setIsInterviewComplete(next.is_finished);
    } catch (questionError) {
      setError("Не удалось получить следующий вопрос. Попробуйте ещё раз.");
    } finally {
      setIsGeneratingQuestion(false);
    }
  }

  async function buildReport() {
    setIsGeneratingReport(true);
    setError("");
    try {
      const result = await generateReport(sessionId, answers);
      setReport(result);
      setScreen("report");
    } catch (reportError) {
      setError("Не удалось сформировать отчёт. Проверьте backend и попробуйте снова.");
    } finally {
      setIsGeneratingReport(false);
    }
  }

  function copyReport() {
    if (report?.markdown_report) {
      navigator.clipboard.writeText(report.markdown_report);
    }
  }

  function downloadReport() {
    if (!report?.markdown_report) {
      return;
    }
    const blob = new Blob([report.markdown_report], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "property-intake-report.md";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="min-h-screen">
      <div className="mx-auto flex w-full max-w-5xl flex-col px-5 py-8 sm:py-12">
        {screen === "landing" && (
          <section className="flex min-h-[70vh] flex-col items-start justify-center">
            <p className="mb-3 rounded-full bg-sky-100 px-3 py-1 text-sm font-medium text-sky-700">
              AI automation / productivity course MVP
            </p>
            <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-slate-950 sm:text-6xl">
              Voice Property Intake Agent
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
              Голосовой AI-агент для первичного интервью собственника
              недвижимости.
            </p>
            <button
              onClick={startInterview}
              className="mt-8 rounded-lg bg-slate-950 px-6 py-3 font-semibold text-white shadow-sm transition hover:bg-slate-800"
            >
              Начать интервью
            </button>
          </section>
        )}

        {screen === "interview" && (
          <section className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-sky-700">
                    Раунд {currentRound}: {ROUND_NAMES[currentRound]} · вопрос{" "}
                    {currentQuestionIndex + 1}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Прогресс: {progressLabel}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                  {isInterviewComplete ? "Интервью завершено" : "Интервью"}
                </span>
              </div>

              {!isInterviewComplete ? (
                <>
                  <h2 className="mt-8 text-2xl font-semibold leading-9 text-slate-950">
                    {currentQuestion}
                  </h2>

                  <div className="mt-6 flex flex-wrap gap-3">
                    {!isRecording ? (
                      <button
                        onClick={startRecording}
                        disabled={isTranscribing || isGeneratingQuestion}
                        className="rounded-lg bg-sky-600 px-5 py-3 font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                      >
                        Записать аудио
                      </button>
                    ) : (
                      <button
                        onClick={stopRecording}
                        className="rounded-lg bg-red-600 px-5 py-3 font-semibold text-white transition hover:bg-red-700"
                      >
                        Остановить запись
                      </button>
                    )}
                    <button
                      onClick={saveAnswerAndContinue}
                      disabled={isRecording || isTranscribing || isGeneratingQuestion}
                      className="rounded-lg border border-slate-300 px-5 py-3 font-semibold text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                    >
                      Сохранить ответ и продолжить
                    </button>
                  </div>

                  <StatusLine
                    isRecording={isRecording}
                    isTranscribing={isTranscribing}
                    isGeneratingQuestion={isGeneratingQuestion}
                  />

                  <label className="mt-6 block text-sm font-medium text-slate-700">
                    Распознанный текст
                  </label>
                  <textarea
                    value={transcript}
                    onChange={(event) => setTranscript(event.target.value)}
                    rows={6}
                    placeholder="После записи здесь появится расшифровка. Текст можно исправить вручную."
                    className="mt-2 w-full resize-y rounded-lg border border-slate-300 bg-white p-4 leading-7 outline-none ring-sky-200 transition focus:ring-4"
                  />
                </>
              ) : (
                <div className="mt-8">
                  <h2 className="text-2xl font-semibold text-slate-950">
                    Все {TOTAL_QUESTIONS} вопросов пройдены
                  </h2>
                  <p className="mt-3 text-slate-600">
                    Теперь можно сформировать итоговый Markdown-отчёт для
                    риэлтора.
                  </p>
                  <button
                    onClick={buildReport}
                    disabled={isGeneratingReport}
                    className="mt-6 rounded-lg bg-slate-950 px-6 py-3 font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    {isGeneratingReport ? "Формируем отчёт..." : "Сформировать отчёт"}
                  </button>
                </div>
              )}

              {error && (
                <p className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {error}
                </p>
              )}
            </div>

            <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-950">Ответы</h3>
              <div className="mt-4 space-y-4">
                {answers.length === 0 && (
                  <p className="text-sm leading-6 text-slate-500">
                    Пока ответов нет. После сохранения они появятся здесь.
                  </p>
                )}
                {answers.map((item, index) => (
                  <div key={`${item.round}-${index}`} className="border-t pt-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Раунд {item.round}
                      {ROUND_NAMES[item.round] ? ` · ${ROUND_NAMES[item.round]}` : ""}
                    </p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                      {item.question}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {item.answer}
                    </p>
                  </div>
                ))}
              </div>
            </aside>
          </section>
        )}

        {screen === "report" && report && (
          <section className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-sky-700">
                  Итог интервью
                </p>
                <h1 className="mt-2 text-3xl font-bold text-slate-950">
                  Отчёт для риэлтора
                </h1>
              </div>
              <button
                onClick={startInterview}
                className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-800 transition hover:bg-white"
              >
                Начать заново
              </button>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
              <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={downloadReport}
                    className="rounded-lg bg-slate-950 px-4 py-2 font-semibold text-white transition hover:bg-slate-800"
                  >
                    Скачать отчёт .md
                  </button>
                  <button
                    onClick={copyReport}
                    className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-800 transition hover:bg-slate-50"
                  >
                    Скопировать отчёт
                  </button>
                </div>
                <pre className="mt-6 max-h-[640px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-5 text-sm leading-7 text-slate-50">
                  {report.markdown_report}
                </pre>
              </div>

              <aside className="space-y-4">
                <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="font-semibold text-slate-950">
                    Карточка клиента
                  </h3>
                  <InfoRow label="Имя" value={report.client_card.name} />
                  <InfoRow label="Телефон / email" value={report.client_card.contact} />
                  <InfoRow
                    label="Собственники"
                    value={report.client_card.ownership_status}
                  />
                  <InfoRow label="Тип" value={report.client_card.property_type} />
                  <InfoRow label="Локация" value={report.client_card.location} />
                  <InfoRow label="Цель" value={report.client_card.goal} />
                  <InfoRow
                    label="Ожидания"
                    value={report.client_card.expected_price}
                  />
                </div>
                <LeadBadge lead={report.lead_score} />
              </aside>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function StatusLine({
  isRecording,
  isTranscribing,
  isGeneratingQuestion,
}: {
  isRecording: boolean;
  isTranscribing: boolean;
  isGeneratingQuestion: boolean;
}) {
  const message = isRecording
    ? "Идёт запись..."
    : isTranscribing
      ? "Распознаём аудио..."
      : isGeneratingQuestion
        ? "Генерируем следующий вопрос..."
        : "";

  if (!message) {
    return null;
  }

  return (
    <p className="mt-4 rounded-lg bg-sky-50 p-3 text-sm font-medium text-sky-700">
      {message}
    </p>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-sm leading-6 text-slate-800">
        {value || "Не указано"}
      </p>
    </div>
  );
}
