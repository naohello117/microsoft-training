const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface Exam {
  exam_id: string;
  exam_name: string;
  path_count: number;
}

export interface LearningPath {
  id: string;
  title: string;
  url: string;
  modules: Module[];
  exam_id?: string;
  exam_name?: string;
}

export interface Module {
  id: string;
  title: string;
  url: string;
  order: number;
  unit_count: number;
}

export interface Unit {
  id: string;
  module_id: string;
  title: string;
  url: string;
  order: number;
  summary_ja?: string;
  raw_content?: string;
  is_scraped: boolean;
}

export interface Quiz {
  id: string;
  unit_id: string;
  question: string;
  choices: { key: string; text: string }[];
  correct_key: string;
  explanation: string;
}

export interface Progress {
  user_id: string;
  learning_path_id: string;
  completed_units: string[];
  quiz_results: { quiz_id: string; is_correct: boolean }[];
  total_score: number;
}

export const api = {
  listExams: () =>
    apiFetch<Exam[]>("/exams"),

  listLearningPaths: (examId?: string) =>
    apiFetch<LearningPath[]>(examId ? `/learning-paths?exam_id=${examId}` : "/learning-paths"),

  scrapeUrl: (url: string, examId?: string, examName?: string) =>
    apiFetch<{
      status: string;
      paths: { learning_path_id: string; title: string }[];
      exam_id?: string | null;
      exam_name?: string | null;
    }>("/scrape", {
      method: "POST",
      body: JSON.stringify({ url, exam_id: examId, exam_name: examName }),
    }),

  tagExam: (pathId: string, examId: string, examName: string) =>
    apiFetch<{ status: string }>(`/learning-paths/${pathId}`, {
      method: "PATCH",
      body: JSON.stringify({ exam_id: examId, exam_name: examName }),
    }),

  getLearningPath: (pathId: string) =>
    apiFetch<LearningPath>(`/learning-path/${pathId}`),

  getModuleUnits: (moduleId: string) =>
    apiFetch<Unit[]>(`/units/${moduleId}`),

  getContent: (unitId: string, force = false) =>
    apiFetch<Unit>(`/content/${unitId}${force ? "?force=true" : ""}`),

  summarizeUnit: (unitId: string, force = false) =>
    apiFetch<Unit>(`/summarize/${unitId}${force ? "?force=true" : ""}`, {
      method: "POST",
    }),

  generateQuiz: (unitId: string) =>
    apiFetch<Quiz[]>(`/quiz/${unitId}`, { method: "POST" }),

  // ポーリング用: 既存のクイズを取得するだけ（生成しない）
  listQuizzes: (unitId: string) =>
    apiFetch<Quiz[]>(`/quiz/${unitId}`, { method: "GET" }),

  getProgress: (userId: string, learningPathId = "az-500") =>
    apiFetch<Progress>(`/progress/${userId}?learning_path_id=${learningPathId}`),

  saveProgress: (
    userId: string,
    data: { unit_id?: string; learning_path_id?: string; quiz_result?: object }
  ) =>
    apiFetch<Progress>(`/progress/${userId}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
