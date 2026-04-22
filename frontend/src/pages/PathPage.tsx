import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, LearningPath, Unit } from "../api/client";

const s = {
  page: { maxWidth: 900, margin: "0 auto", padding: "1.5rem", fontFamily: "sans-serif" } as const,
  back: { background: "none", border: "none", color: "#0078d4", cursor: "pointer", fontSize: "0.9rem", padding: 0, marginBottom: "1rem" } as const,
  card: { border: "1px solid #e1e4e8", borderRadius: 6, marginBottom: "0.75rem", overflow: "hidden" } as const,
  cardHeader: { background: "#f6f8fa", padding: "0.6rem 1rem", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" } as const,
  unitRow: (done: boolean) => ({ display: "flex", alignItems: "center", padding: "0.4rem 1rem 0.4rem 1.5rem", borderTop: "1px solid #eee", background: done ? "#f0fff4" : "#fff", gap: "0.5rem", cursor: "pointer" } as const),
  badge: (color: string) => ({ fontSize: "0.7rem", padding: "2px 6px", borderRadius: 10, background: color, color: "#fff", whiteSpace: "nowrap" as const }),
  learnBtn: { padding: "0.3rem 0.75rem", background: "#0078d4", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: "0.85rem" } as const,
};

export default function PathPage() {
  const { pathId = "" } = useParams<{ pathId: string }>();
  const navigate = useNavigate();
  const [path, setPath] = useState<LearningPath | null>(null);
  const [openModule, setOpenModule] = useState<string | null>(null);
  const [unitMap, setUnitMap] = useState<Record<string, Unit[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listLearningPaths().then(paths => {
      const found = paths.find(p => p.id === pathId) ?? null;
      setPath(found);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [pathId]);

  async function toggleModule(moduleId: string) {
    if (openModule === moduleId) { setOpenModule(null); return; }
    setOpenModule(moduleId);
    if (!unitMap[moduleId]) {
      const units = await api.getModuleUnits(moduleId);
      setUnitMap(prev => ({ ...prev, [moduleId]: units }));
    }
  }

  const backExamId = path?.exam_id;

  if (loading) return <div style={s.page}><p>読み込み中...</p></div>;
  if (!path) return <div style={s.page}><p>ラーニングパスが見つかりません</p></div>;

  return (
    <div style={s.page}>
      <button
        style={s.back}
        onClick={() => navigate(backExamId ? `/exam/${backExamId}` : "/")}
      >
        ← {backExamId ? `${(path.exam_name ?? backExamId).toUpperCase()} に戻る` : "試験一覧に戻る"}
      </button>

      <h2 style={{ marginBottom: "0.25rem" }}>{path.title}</h2>
      <p style={{ color: "#666", marginTop: 0, marginBottom: "1.25rem" }}>
        {(path.modules ?? []).length} モジュール — 学習するユニットを選択してください
      </p>

      {(path.modules ?? []).map(mod => (
        <div key={mod.id} style={s.card}>
          <div style={s.cardHeader} onClick={() => toggleModule(mod.id)}>
            <span style={{ fontWeight: 500 }}>{mod.title}</span>
            <span style={{ color: "#666", fontSize: "0.85rem" }}>
              {mod.unit_count} ユニット　{openModule === mod.id ? "▲" : "▼"}
            </span>
          </div>
          {openModule === mod.id && (
            <div>
              {(unitMap[mod.id] ?? []).length === 0
                ? <p style={{ padding: "0.5rem 1rem", color: "#888" }}>読み込み中...</p>
                : (unitMap[mod.id] ?? []).map(unit => (
                  <div
                    key={unit.id}
                    style={s.unitRow(!!unit.summary_ja)}
                    onClick={() => navigate(`/unit/${unit.id}`)}
                  >
                    <span style={{ flex: 1, fontSize: "0.9rem" }}>{unit.title}</span>
                    {unit.summary_ja
                      ? <span style={s.badge("#28a745")}>要約済</span>
                      : <span style={s.badge("#6c757d")}>未要約</span>}
                    <button style={s.learnBtn}>学習 →</button>
                  </div>
                ))
              }
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
