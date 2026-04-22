import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, Exam } from "../api/client";

const EXAM_META: Record<string, { color: string; desc: string }> = {
  "az-500": { color: "#0078d4", desc: "Microsoft Azure Security Technologies" },
  "sc-300": { color: "#107c41", desc: "Microsoft Identity and Access Administrator" },
  "sc-100": { color: "#8764b8", desc: "Microsoft Cybersecurity Architect" },
};

const s = {
  page: { maxWidth: 900, margin: "0 auto", padding: "2rem", fontFamily: "sans-serif" } as const,
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "1rem", marginTop: "1.5rem" } as const,
  card: (color: string) => ({
    border: `2px solid ${color}`,
    borderRadius: 8,
    padding: "1.5rem",
    cursor: "pointer",
    transition: "box-shadow 0.15s",
    background: "#fff",
  } as const),
  examId: (color: string) => ({
    display: "inline-block",
    background: color,
    color: "#fff",
    fontWeight: "bold",
    fontSize: "1.1rem",
    padding: "0.2rem 0.6rem",
    borderRadius: 4,
    marginBottom: "0.5rem",
  } as const),
  desc: { color: "#555", fontSize: "0.9rem", marginBottom: "0.75rem" } as const,
  count: { fontSize: "0.8rem", color: "#888" } as const,
};

export default function ExamListPage() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<Exam[]>([]);

  useEffect(() => {
    api.listExams().then(setExams).catch(() => setExams([]));
  }, []);

  // Merge API exams with static meta (show known exams even if no paths yet)
  const knownExams = ["az-500", "sc-300", "sc-100"];
  const examMap: Record<string, Exam> = {};
  for (const e of exams) examMap[e.exam_id] = e;
  for (const id of knownExams) {
    if (!examMap[id]) examMap[id] = { exam_id: id, exam_name: id.toUpperCase(), path_count: 0 };
  }
  const displayExams = Object.values(examMap).sort((a, b) =>
    knownExams.indexOf(a.exam_id) - knownExams.indexOf(b.exam_id)
  );

  return (
    <div style={s.page}>
      <h2 style={{ marginBottom: "0.25rem" }}>試験コレクション</h2>
      <p style={{ color: "#666", marginTop: 0 }}>学習したい試験を選択してください</p>

      <div style={s.grid}>
        {displayExams.map((exam) => {
          const meta = EXAM_META[exam.exam_id] ?? { color: "#6c757d", desc: "" };
          return (
            <div
              key={exam.exam_id}
              style={s.card(meta.color)}
              onClick={() => navigate(`/exam/${exam.exam_id}`)}
              onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)")}
              onMouseLeave={e => (e.currentTarget.style.boxShadow = "none")}
            >
              <div style={s.examId(meta.color)}>{exam.exam_name}</div>
              <p style={s.desc}>{meta.desc}</p>
              <span style={s.count}>
                {exam.path_count > 0 ? `${exam.path_count} ラーニングパス` : "ラーニングパスなし"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
