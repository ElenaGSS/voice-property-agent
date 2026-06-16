export type AnswerItem = {
  round: number;
  question: string;
  answer: string;
};

export type NextQuestionRequest = {
  session_id: string;
  current_round: number;
  current_question_index: number;
  answers: AnswerItem[];
};

export type NextQuestionResponse = {
  question: string;
  round: number;
  question_index: number;
  is_finished: boolean;
};

export type ClientCard = {
  name: string;
  contact: string;
  ownership_status: string;
  property_type: string;
  location: string;
  goal: string;
  expected_price: string;
};

export type LeadScore = {
  label: "HOT" | "WARM" | "INFO";
  title: string;
  reason: string;
};

export type ReportResponse = {
  client_card: ClientCard;
  lead_score: LeadScore;
  markdown_report: string;
  used_tools?: string[];
  tool_results?: Record<string, ToolResult>;
};

export type ToolResult = {
  tool_name?: string;
  status?: "success" | "calculation_completed" | "insufficient_data" | string;
  reason?: string;
  [key: string]: string | number | null | undefined;
};
