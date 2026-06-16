"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { LeadBadge } from "@/components/LeadBadge";
import {
  fetchNextQuestion,
  generateReport,
  transcribeAudio,
} from "@/services/api";
import { AnswerItem, ReportResponse, ToolResult } from "@/types/interview";

const INTERVIEW_MODE =
  process.env.NEXT_PUBLIC_INTERVIEW_MODE === "full" ? "full" : "demo";
const TOTAL_QUESTIONS = INTERVIEW_MODE === "full" ? 12 : 7;
const DEMO_RECORDING_LIMIT_MS = 12_000;
const TRANSCRIBE_TIMEOUT_MS = 45_000;
const INVALID_CONTACT_MESSAGE =
  "Номер распознан некорректно. Введите вручную или повторите запись.";
const FIRST_QUESTION = "Как вас зовут?";
const FULL_ROUND_NAMES: Record<number, string> = {
  1: "Контактные данные",
  2: "Объект",
  3: "Продажа",
  4: "Аренда, ожидания и важные обстоятельства",
};
const DEMO_ROUND_NAMES: Record<number, string> = {
  1: "Демо-опрос для расчёта",
};
const ROUND_NAMES = INTERVIEW_MODE === "full" ? FULL_ROUND_NAMES : DEMO_ROUND_NAMES;

type SavedAnswer = AnswerItem & {
  question_index: number;
};

function createSessionId() {
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toApiAnswers(answers: SavedAnswer[]): AnswerItem[] {
  return answers.map(({ round, question, answer }) => ({
    round,
    question,
    answer,
  }));
}

export default function Home() {
  const [screen, setScreen] = useState<"landing" | "interview" | "report">(
    "landing",
  );
  const [sessionId, setSessionId] = useState(createSessionId);
  const [currentRound, setCurrentRound] = useState(1);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(FIRST_QUESTION);
  const [answers, setAnswers] = useState<SavedAnswer[]>([]);
  const [transcript, setTranscript] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isGeneratingQuestion, setIsGeneratingQuestion] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [isInterviewComplete, setIsInterviewComplete] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const processingStartedAtRef = useRef<number | null>(null);
  const recordingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcribeAbortControllerRef = useRef<AbortController | null>(null);
  const transcribeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcribeAbortReasonRef = useRef<"manual" | "timeout" | "silent" | null>(
    null,
  );

  const progressLabel = useMemo(
    () => `${answers.length + (isInterviewComplete ? 0 : 1)} / ${TOTAL_QUESTIONS}`,
    [answers.length, isInterviewComplete],
  );
  const hasInvalidContactTranscript = transcript.includes(INVALID_CONTACT_MESSAGE);

  useEffect(() => {
    if (!isTranscribing && !isGeneratingQuestion && !isGeneratingReport) {
      processingStartedAtRef.current = null;
      return;
    }

    if (!processingStartedAtRef.current) {
      processingStartedAtRef.current = Date.now();
    }

    const timer = window.setInterval(() => {
      if (processingStartedAtRef.current) {
        setElapsedSeconds(Math.floor((Date.now() - processingStartedAtRef.current) / 1000));
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isTranscribing, isGeneratingQuestion, isGeneratingReport]);

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
    clearRecordingTimeout();
    cancelActiveTranscription(false);
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
        clearRecordingTimeout();
        const audioBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        streamRef.current?.getTracks().forEach((track) => track.stop());
        setIsRecording(false);
        await handleTranscription(audioBlob);
      };

      recorder.start();
      setIsRecording(true);
      if (INTERVIEW_MODE === "demo") {
        recordingTimeoutRef.current = setTimeout(() => {
          stopRecording();
        }, DEMO_RECORDING_LIMIT_MS);
      }
    } catch (recordingError) {
      setError(
        "Не удалось получить доступ к микрофону. Проверьте разрешения браузера.",
      );
    }
  }

  function stopRecording() {
    clearRecordingTimeout();
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    setIsRecording(false);
  }

  function clearRecordingTimeout() {
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }
  }

  async function handleTranscription(audioBlob: Blob) {
    setIsTranscribing(true);
    processingStartedAtRef.current = Date.now();
    setElapsedSeconds(0);
    setError("");
    const abortController = new AbortController();
    transcribeAbortControllerRef.current = abortController;
    transcribeAbortReasonRef.current = null;
    transcribeTimeoutRef.current = setTimeout(() => {
      transcribeAbortReasonRef.current = "timeout";
      abortController.abort();
    }, TRANSCRIBE_TIMEOUT_MS);

    try {
      const text = await transcribeAudio(
        audioBlob,
        currentQuestion,
        abortController.signal,
      );
      setTranscript(text);
    } catch (transcriptionError) {
      if (
        transcriptionError instanceof Error &&
        transcriptionError.message === "TRANSCRIBE_ABORTED"
      ) {
        if (transcribeAbortReasonRef.current === "timeout") {
          setError(
            "Распознавание заняло слишком много времени. Повторите запись или введите ответ вручную.",
          );
        } else if (transcribeAbortReasonRef.current === "manual") {
          setError("Распознавание отменено. Можно повторить запись или ввести ответ вручную.");
        }
      } else {
        setError(
          "Сервер не смог обработать аудио. Можно включить демонстрационный режим распознавания или ввести ответ вручную.",
        );
      }
    } finally {
      clearTranscribeTimeout();
      transcribeAbortControllerRef.current = null;
      transcribeAbortReasonRef.current = null;
      processingStartedAtRef.current = null;
      setElapsedSeconds(0);
      setIsTranscribing(false);
    }
  }

  function cancelActiveTranscription(showMessage = true) {
    if (!transcribeAbortControllerRef.current) {
      return;
    }
    transcribeAbortReasonRef.current = showMessage ? "manual" : "silent";
    transcribeAbortControllerRef.current.abort();
    clearTranscribeTimeout();
    processingStartedAtRef.current = null;
    setElapsedSeconds(0);
    setIsTranscribing(false);
    if (showMessage) {
      setError("Распознавание отменено. Можно повторить запись или ввести ответ вручную.");
    }
  }

  function clearTranscribeTimeout() {
    if (transcribeTimeoutRef.current) {
      clearTimeout(transcribeTimeoutRef.current);
      transcribeTimeoutRef.current = null;
    }
  }

  async function saveAnswerAndContinue() {
    if (!transcript.trim()) {
      setError("Добавьте ответ: запишите аудио или введите текст вручную.");
      return;
    }
    if (hasInvalidContactTranscript) {
      setError("Исправьте контакт вручную или повторите запись.");
      return;
    }

    const cleanedTranscript = cleanAnswerBeforeSave(transcript);
    if (!cleanedTranscript) {
      setError("Добавьте ответ: запишите аудио или введите текст вручную.");
      return;
    }
    const updatedAnswers = [
      ...answers,
      {
        round: currentRound,
        question: currentQuestion,
        answer: cleanedTranscript,
        question_index: currentQuestionIndex,
      },
    ];
    setAnswers(updatedAnswers);
    setTranscript("");
    setError("");

    if (updatedAnswers.length >= TOTAL_QUESTIONS) {
      setIsInterviewComplete(true);
      if (INTERVIEW_MODE === "demo") {
        await buildReport(updatedAnswers);
      }
      return;
    }

    setIsGeneratingQuestion(true);
    processingStartedAtRef.current = Date.now();
    setElapsedSeconds(0);
    try {
      const next = await fetchNextQuestion({
        session_id: sessionId,
        current_round: currentRound,
        current_question_index: currentQuestionIndex,
        answers: toApiAnswers(updatedAnswers),
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

  function goToPreviousQuestion() {
    const previousAnswer = answers[answers.length - 1];
    if (!previousAnswer) {
      return;
    }

    setAnswers(answers.slice(0, -1));
    setCurrentRound(previousAnswer.round);
    setCurrentQuestionIndex(previousAnswer.question_index);
    setCurrentQuestion(previousAnswer.question);
    setTranscript(previousAnswer.answer);
    setIsInterviewComplete(false);
    setError("");
  }

  async function buildReport(reportAnswers = answers) {
    setIsGeneratingReport(true);
    processingStartedAtRef.current = Date.now();
    setElapsedSeconds(0);
    setError("");
    try {
      const result = await generateReport(sessionId, toApiAnswers(reportAnswers));
      setReport(result);
      setScreen("report");
    } catch (reportError) {
      setError("Не удалось сформировать отчёт. Проверьте сервер и попробуйте снова.");
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
    <main className="mediterranean-shell min-h-screen">
      <div className="mx-auto flex w-full max-w-6xl flex-col px-5 py-8 sm:py-12">
        {screen === "landing" && (
          <section className="grid min-h-[76vh] items-center gap-10 lg:grid-cols-[1.08fr_0.92fr]">
            <div className="max-w-3xl">
              <p className="mb-4 inline-flex rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-sm font-semibold text-[#173b63] shadow-sm">
                Voice Property Intake Agent · MVP
              </p>
              <h1 className="text-4xl font-bold tracking-tight text-slate-950 sm:text-6xl">
                Голосовой AI-агент по недвижимости
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-700">
                Профессиональный голосовой AI-опрос собственника недвижимости:
                контакты, детали объекта, мотивация, ожидания и структурированный
                отчёт для риэлтора.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <button
                  onClick={startInterview}
                  className="primary-action rounded-lg px-7 py-4 font-semibold text-white transition duration-200"
                >
                  Начать интервью
                </button>
                <span className="rounded-full bg-white/80 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">
                  7 вопросов · автоматический расчёт · Markdown-отчёт
                </span>
              </div>
            </div>

            <div className="glass-panel p-4 sm:p-5">
              <div className="summary-preview p-5 sm:p-6">
                <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-5">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Предварительная карточка
                    </p>
                    <h2 className="mt-2 text-xl font-semibold text-slate-950">
                      Бриф собственника
                    </h2>
                  </div>
                  <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-800 ring-1 ring-teal-100">
                    Готово
                  </span>
                </div>

                <div className="mt-5 space-y-3">
                  {[
                    [
                      "Контактные данные",
                      "Имя, телефон или email, статус собственника",
                    ],
                    ["Детали объекта", "Локация, тип, описание собственника"],
                    [
                      "Мотивация",
                      "Продажа или аренда, причина, важный контекст",
                    ],
                    ["Оценка лида", "HOT / WARM / INFO с кратким объяснением"],
                    ["Markdown-отчёт", "Структурированное резюме для риэлтора"],
                  ].map(([title, description]) => (
                    <div
                      key={title}
                      className="summary-row flex items-start gap-3 p-4"
                    >
                      <span className="summary-dot mt-2 shrink-0" />
                      <div>
                        <p className="font-semibold text-slate-900">{title}</p>
                        <p className="mt-1 text-sm leading-6 text-slate-500">
                          {description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-5 rounded-lg border border-slate-200 bg-[#173b63] p-4 text-white shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-100">
                    Следующий шаг
                  </p>
                  <p className="mt-2 text-sm leading-6 text-blue-50">
                    Сформировать краткий Markdown-отчёт и передать заявку
                    консультанту.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {screen === "interview" && (
          <section className="grid gap-6 lg:grid-cols-[1fr_340px]">
            <div className="soft-card rounded-lg p-6 sm:p-7">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-sky-800">
                    Раунд {currentRound}: {ROUND_NAMES[currentRound]} · вопрос{" "}
                    {currentQuestionIndex + 1}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Прогресс: {progressLabel}
                  </p>
                </div>
                <span className="rounded-full bg-slate-50 px-3 py-1 text-sm font-medium text-[#173b63] ring-1 ring-slate-200">
                  {isInterviewComplete ? "Интервью завершено" : "Интервью"}
                </span>
              </div>

              <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#173b63] to-teal-700 transition-all duration-500"
                  style={{
                    width: `${
                      ((answers.length + (isInterviewComplete ? 0 : 1)) /
                        TOTAL_QUESTIONS) *
                      100
                    }%`,
                  }}
                />
              </div>

              {!isInterviewComplete ? (
                <>
                  <div className="mt-8 rounded-lg border border-slate-200 bg-white/80 p-5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#173b63]">
                      Текущий вопрос
                    </p>
                    <h2 className="mt-3 text-2xl font-semibold leading-9 text-slate-950">
                      {currentQuestion}
                    </h2>
                  </div>

                  <div className="mt-6 flex flex-wrap gap-3">
                    {!isRecording ? (
                      <button
                        onClick={startRecording}
                        disabled={isTranscribing || isGeneratingQuestion}
                        className="primary-action rounded-lg px-5 py-3 font-semibold text-white transition duration-200 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
                      >
                        Записать аудио
                      </button>
                    ) : (
                      <button
                        onClick={stopRecording}
                        className="rounded-lg bg-red-500 px-5 py-3 font-semibold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-red-600"
                      >
                        Остановить запись
                      </button>
                    )}
                    <button
                      onClick={goToPreviousQuestion}
                      disabled={
                        answers.length === 0 ||
                        isRecording ||
                        isTranscribing ||
                        isGeneratingQuestion
                      }
                      className="rounded-lg border border-slate-200 bg-white/70 px-5 py-3 font-semibold text-slate-700 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:translate-y-0"
                    >
                      Назад
                    </button>
                    <button
                      onClick={saveAnswerAndContinue}
                      disabled={
                        isRecording ||
                        isTranscribing ||
                        isGeneratingQuestion ||
                        hasInvalidContactTranscript
                      }
                      className="rounded-lg border border-slate-200 bg-white/80 px-5 py-3 font-semibold text-slate-800 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-sky-200 hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:translate-y-0"
                    >
                      Сохранить ответ и продолжить
                    </button>
                    {isTranscribing && (
                      <button
                        onClick={() => cancelActiveTranscription()}
                        className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-3 font-semibold text-amber-800 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-amber-100"
                      >
                        Отменить распознавание
                      </button>
                    )}
                  </div>
                  {INTERVIEW_MODE === "demo" && (
                    <p className="mt-3 text-sm leading-6 text-slate-500">
                      Для короткого ответа достаточно 3–8 секунд. Запись
                      остановится автоматически через 12 секунд.
                    </p>
                  )}

                  <StatusLine
                    isRecording={isRecording}
                    isTranscribing={isTranscribing}
                    isGeneratingQuestion={isGeneratingQuestion}
                    isGeneratingReport={false}
                    elapsedSeconds={elapsedSeconds}
                  />

                  <label className="mt-6 block text-sm font-medium text-slate-700">
                    Распознанный текст
                  </label>
                  <textarea
                    value={transcript}
                    onChange={(event) => setTranscript(event.target.value)}
                    rows={6}
                    placeholder="После записи здесь появится расшифровка. Текст можно исправить вручную."
                    className="mt-2 w-full resize-y rounded-lg border border-slate-200 bg-white/90 p-4 leading-7 shadow-inner outline-none ring-sky-200 transition focus:border-sky-300 focus:ring-4"
                  />
                  {hasInvalidContactTranscript && (
                    <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
                      Номер распознан некорректно. Введите контакт вручную или
                      повторите запись.
                    </p>
                  )}
                </>
              ) : (
                <div className="mt-8 rounded-lg border border-slate-200 bg-white/80 p-5">
                  <h2 className="text-2xl font-semibold text-slate-950">
                    Все {TOTAL_QUESTIONS} вопросов пройдены
                  </h2>
                  <p className="mt-3 text-slate-600">
                    Теперь можно сформировать итоговый Markdown-отчёт для
                    риэлтора.
                  </p>
                  <div className="mt-6 flex flex-wrap gap-3">
                    <button
                      onClick={goToPreviousQuestion}
                      disabled={isGeneratingReport || answers.length === 0}
                      className="rounded-lg border border-slate-200 bg-white/80 px-5 py-3 font-semibold text-slate-800 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:translate-y-0"
                    >
                      Назад
                    </button>
                    <button
                      onClick={() => buildReport()}
                      disabled={isGeneratingReport}
                      className="primary-action rounded-lg px-6 py-3 font-semibold text-white transition duration-200 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
                    >
                      {isGeneratingReport ? "Формируем отчёт..." : "Сформировать отчёт"}
                    </button>
                  </div>
                  <StatusLine
                    isRecording={false}
                    isTranscribing={false}
                    isGeneratingQuestion={false}
                    isGeneratingReport={isGeneratingReport}
                    elapsedSeconds={elapsedSeconds}
                  />
                </div>
              )}

              {error && (
                <p className="mt-5 rounded-lg border border-red-200 bg-red-50/90 p-3 text-sm text-red-700 shadow-sm">
                  {error}
                </p>
              )}
            </div>

            <aside className="soft-card rounded-lg p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold text-slate-950">Ответы</h3>
                <span className="rounded-full bg-slate-50 px-3 py-1 text-xs font-semibold text-[#173b63] ring-1 ring-slate-200">
                  {answers.length}/{TOTAL_QUESTIONS}
                </span>
              </div>
              <div className="mt-4 space-y-4">
                {answers.length === 0 && (
                  <p className="rounded-lg bg-slate-50 p-4 text-sm leading-6 text-slate-500">
                    Пока ответов нет. После сохранения они появятся здесь.
                  </p>
                )}
                {answers.map((item, index) => (
                  <div
                    key={`${item.round}-${index}`}
                    className="rounded-lg border border-slate-100 bg-white/80 p-4 shadow-sm"
                  >
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#173b63]">
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
                <p className="text-sm font-semibold text-sky-800">
                  Итог интервью
                </p>
                <h1 className="mt-2 text-3xl font-bold text-slate-950">
                  Отчёт для риэлтора
                </h1>
              </div>
              <button
                onClick={startInterview}
                className="rounded-lg border border-slate-200 bg-white/80 px-4 py-2 font-semibold text-slate-800 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-white"
              >
                Начать заново
              </button>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
              <div className="soft-card rounded-lg p-6">
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={downloadReport}
                    className="primary-action rounded-lg px-4 py-2 font-semibold text-white transition duration-200"
                  >
                    Скачать отчёт .md
                  </button>
                  <button
                    onClick={copyReport}
                    className="rounded-lg border border-slate-200 bg-white/80 px-4 py-2 font-semibold text-slate-800 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-white"
                  >
                    Скопировать отчёт
                  </button>
                </div>
                <pre className="mt-6 max-h-[640px] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white/90 p-5 text-sm leading-7 text-slate-700 shadow-inner">
                  {report.markdown_report}
                </pre>
              </div>

              <aside className="space-y-4">
                <div className="soft-card rounded-lg p-5">
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
                <ToolResultsCard report={report} />
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
  isGeneratingReport,
  elapsedSeconds,
}: {
  isRecording: boolean;
  isTranscribing: boolean;
  isGeneratingQuestion: boolean;
  isGeneratingReport: boolean;
  elapsedSeconds: number;
}) {
  if (isRecording) {
    return (
      <p className="mt-4 rounded-lg border border-sky-100 bg-sky-50/90 p-3 text-sm font-semibold text-sky-800 shadow-sm">
        Идёт запись...
      </p>
    );
  }

  if (!isTranscribing && !isGeneratingQuestion && !isGeneratingReport) {
    return null;
  }

  const activeIndex = isTranscribing
    ? elapsedSeconds < 2
      ? 0
      : 1
    : isGeneratingQuestion
      ? elapsedSeconds < 2
        ? 2
        : 3
      : 3;

  const stages = [
    "Аудио получено",
    "Распознаём голос",
    "Анализируем ответ",
    isGeneratingReport ? "Формируем отчёт" : "Подбираем следующий вопрос",
  ];

  return (
    <div className="mt-4 rounded-lg border border-sky-100 bg-sky-50/90 p-4 text-sm text-slate-700 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-sky-900">{stages[activeIndex]}</p>
        <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-sky-800 ring-1 ring-sky-100">
          {formatElapsed(elapsedSeconds)}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        {stages.map((stage, index) => (
          <div
            key={stage}
            className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
              index <= activeIndex
                ? "border-sky-200 bg-white text-sky-800"
                : "border-slate-200 bg-white/50 text-slate-400"
            }`}
          >
            {stage}
          </div>
        ))}
      </div>
      <p className="mt-3 leading-6 text-slate-600">
        Обычно это занимает 20–45 секунд на бесплатном сервере Hugging Face.
      </p>
      <p className="mt-1 leading-6 text-slate-500">
        Первый ответ может занять дольше, потому что модель распознавания голоса
        запускается после простоя.
      </p>
    </div>
  );
}

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const rest = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${rest}`;
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

function ToolResultsCard({ report }: { report: ReportResponse }) {
  const usedTools = report.used_tools ?? [];
  const toolResults = report.tool_results ?? {};
  const entries = Object.entries(toolResults);
  const successfulToolNames = usedTools.filter((toolName) =>
    isToolSuccessStatus(toolResults[toolName]?.status),
  );
  const successfulEntries = entries.filter(([, result]) =>
    isToolSuccessStatus(result.status),
  );
  const insufficientEntries = entries.filter(
    ([, result]) => !isToolSuccessStatus(result.status),
  );

  return (
    <div className="soft-card rounded-lg p-5">
      <h3 className="font-semibold text-slate-950">Использованные инструменты</h3>
      {successfulToolNames.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {successfulToolNames.map((toolName) => (
            <span
              key={toolName}
              className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-800 ring-1 ring-teal-100"
            >
              {toolName}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">
          Инструменты не использованы: недостаточно данных для расчётов.
        </p>
      )}

      <div className="mt-4 space-y-3">
        {successfulEntries.map(([toolName, result]) => (
          <div
            key={toolName}
            className="rounded-lg border border-slate-100 bg-white/85 p-4 shadow-sm"
          >
            <p className="text-sm font-semibold text-slate-900">{toolName}</p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Расчёт выполнен
            </p>
            <ToolSummary result={result} toolName={toolName} />
          </div>
        ))}
      </div>

      {insufficientEntries.length > 0 && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Недостаточно данных для расчёта
          </p>
          <div className="mt-3 space-y-3">
            {insufficientEntries.map(([toolName, result]) => (
              <div
                key={toolName}
                className="rounded-lg border border-slate-100 bg-slate-50/80 p-3"
              >
                <p className="text-sm font-semibold text-slate-800">{toolName}</p>
                <ToolSummary result={result} toolName={toolName} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ToolSummary({
  result,
  toolName,
}: {
  result: ToolResult;
  toolName: string;
}) {
  const resolvedToolName = result.tool_name || toolName;

  if (!isToolSuccessStatus(result.status)) {
    return (
      <div className="mt-2 space-y-2">
        <p className="text-sm leading-6 text-slate-500">
          {getToolDescription(resolvedToolName)}
        </p>
        <p className="text-sm leading-6 text-slate-600">
          <span className="font-semibold text-slate-800">Недостаточно данных:</span>{" "}
          {getInsufficientReason(resolvedToolName, result.reason)}
        </p>
      </div>
    );
  }

  if (resolvedToolName === "Tax Estimator Tool") {
    return (
      <div className="mt-2 space-y-2">
        <p className="text-sm leading-6 text-slate-500">
          Ориентировочный расчёт налога на прибыль IRPF.
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Покупка: <span className="font-semibold text-slate-950">{formatMoney(result.purchase_price)}</span>{" "}
          → продажа:{" "}
          <span className="font-semibold text-slate-950">{formatMoney(result.sale_price)}</span>
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Прибыль:{" "}
          <span className="font-semibold text-slate-950">
            {formatMoney(result.estimated_capital_gain)}
          </span>{" "}
          · IRPF:{" "}
          <span className="font-semibold text-slate-950">
            {formatMoney(result.estimated_irpf)}
          </span>
        </p>
        <p className="text-xs leading-5 text-slate-500">
          Ориентировочная симуляция, не налоговая консультация.
        </p>
      </div>
    );
  }

  if (resolvedToolName === "Barcelona Market Data Tool") {
    return (
      <div className="mt-2 space-y-2">
        <p className="text-sm leading-6 text-slate-500">
          Рыночное сравнение по району.
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Район:{" "}
          <span className="font-semibold text-slate-950">
            {formatTextValue(result.district)}
          </span>
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Объект:{" "}
          <span className="font-semibold text-slate-950">
            {formatSquareMeterPrice(result.object_price_m2)}
          </span>{" "}
          · район:{" "}
          <span className="font-semibold text-slate-950">
            {formatSquareMeterPrice(result.district_avg_price_m2)}
          </span>{" "}
          · отклонение:{" "}
          <span className="font-semibold text-slate-950">
            {formatSignedPercent(result.deviation_percent)}
          </span>
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Позиция:{" "}
          <span className="font-semibold text-slate-950">
            {formatMarketPosition(result.market_position)}
          </span>
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Срок продажи:{" "}
          <span className="font-semibold text-slate-950">
            {formatTextValue(result.estimated_sale_time)}
          </span>
        </p>
      </div>
    );
  }

  if (resolvedToolName === "Rental Yield Analyzer") {
    return (
      <div className="mt-2 space-y-2">
        <p className="text-sm leading-6 text-slate-500">
          Анализ рентабельности аренды.
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Аренда:{" "}
          <span className="font-semibold text-slate-950">
            {formatMoney(result.monthly_rent)}/мес
          </span>{" "}
          · годовой доход:{" "}
          <span className="font-semibold text-slate-950">
            {formatMoney(result.annual_rent)}
          </span>
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Доходность:{" "}
          <span className="font-semibold text-slate-950">
            {formatPercent(result.gross_yield_percent)}
          </span>{" "}
          · окупаемость:{" "}
          <span className="font-semibold text-slate-950">
            {formatNumber(result.payback_years)} лет
          </span>
        </p>
        <p className="text-sm leading-6 text-slate-700">
          Вывод:{" "}
          <span className="font-semibold text-slate-950">
            {formatYieldCategory(result.yield_category)}
          </span>
        </p>
      </div>
    );
  }

  return null;
}

function getToolDescription(toolName: string) {
  if (toolName === "Tax Estimator Tool") {
    return "Ориентировочный расчёт налога на прибыль IRPF.";
  }
  if (toolName === "Barcelona Market Data Tool") {
    return "Рыночное сравнение по району.";
  }
  if (toolName === "Rental Yield Analyzer") {
    return "Анализ рентабельности аренды.";
  }
  return "Расчёт по данным интервью.";
}

function getInsufficientReason(toolName: string, reason?: string) {
  if (toolName === "Rental Yield Analyzer") {
    return "не указана предполагаемая месячная аренда.";
  }
  return reason || "недостаточно данных для расчёта.";
}

function isToolSuccessStatus(status: string | undefined) {
  return status === "success" || status === "calculation_completed";
}

function formatMoney(value: string | number | null | undefined) {
  if (typeof value !== "number") {
    return "н/д";
  }
  return `${Math.round(value).toLocaleString("ru-RU")} €`;
}

function formatSquareMeterPrice(value: string | number | null | undefined) {
  if (typeof value !== "number") {
    return "н/д";
  }
  return `${Math.round(value).toLocaleString("ru-RU")} €/м²`;
}

function formatPercent(value: string | number | null | undefined) {
  if (typeof value !== "number") {
    return "н/д";
  }
  return `${value.toLocaleString("ru-RU", {
    maximumFractionDigits: 2,
  })}%`;
}

function formatSignedPercent(value: string | number | null | undefined) {
  if (typeof value !== "number") {
    return "н/д";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatPercent(value)}`;
}

function formatNumber(value: string | number | null | undefined) {
  if (typeof value !== "number") {
    return "н/д";
  }
  return value.toLocaleString("ru-RU", {
    maximumFractionDigits: 1,
  });
}

function formatTextValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "н/д";
  }
  return String(value);
}

function formatMarketPosition(value: string | number | null | undefined) {
  return (
    {
      below_market: "ниже рынка",
      near_market: "около рынка",
      above_market: "выше рынка",
      strongly_above_market: "сильно выше рынка",
    }[String(value)] || formatTextValue(value)
  );
}

function formatYieldCategory(value: string | number | null | undefined) {
  return (
    {
      low: "низкая доходность",
      medium: "средняя доходность",
      high: "высокая доходность",
    }[String(value)] || formatTextValue(value)
  );
}

function cleanAnswerBeforeSave(value: string) {
  return value.trim().replace(/[\s.,!?;:]+$/g, "").trim();
}
