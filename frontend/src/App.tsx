import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import ExamListPage from "./pages/ExamListPage";
import ExamPage from "./pages/ExamPage";
import PathPage from "./pages/PathPage";
import UnitPage from "./pages/UnitPage";
import { AuthProvider, useAuth, AUTH_URLS } from "./auth";

function AuthHeaderControls() {
  const { loading, principal, isAdmin } = useAuth();
  if (loading) {
    return <span style={{ fontSize: "0.85rem", opacity: 0.8 }}>認証確認中…</span>;
  }
  if (principal) {
    return (
      <>
        <span style={{ fontSize: "0.85rem" }}>
          {principal.userDetails}
          {isAdmin && (
            <span
              style={{
                background: "rgba(255,255,255,0.25)",
                padding: "0.05rem 0.4rem",
                borderRadius: 3,
                marginLeft: "0.4rem",
                fontSize: "0.75rem",
              }}
            >
              管理者
            </span>
          )}
        </span>
        <a
          href={AUTH_URLS.logout}
          style={{ color: "white", fontSize: "0.85rem", textDecoration: "underline" }}
        >
          サインアウト
        </a>
      </>
    );
  }
  return (
    <a
      href={AUTH_URLS.login}
      style={{ color: "white", fontSize: "0.85rem", textDecoration: "underline" }}
    >
      管理者サインイン
    </a>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <header
          style={{
            background: "#0078d4",
            color: "white",
            padding: "0.75rem 2rem",
            display: "flex",
            alignItems: "center",
            gap: "1rem",
          }}
        >
          <Link
            to="/"
            style={{ color: "white", textDecoration: "none", fontWeight: "bold", fontSize: "1.05rem" }}
          >
            Microsoft Learn 学習サポート
          </Link>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <AuthHeaderControls />
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<ExamListPage />} />
            <Route path="/exam/:examId" element={<ExamPage />} />
            <Route path="/path/:pathId" element={<PathPage />} />
            <Route path="/unit/:unitId" element={<UnitPage />} />
          </Routes>
        </main>
      </BrowserRouter>
    </AuthProvider>
  );
}
