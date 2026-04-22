import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import ExamListPage from "./pages/ExamListPage";
import ExamPage from "./pages/ExamPage";
import PathPage from "./pages/PathPage";
import UnitPage from "./pages/UnitPage";

export default function App() {
  return (
    <BrowserRouter>
      <header style={{ background: "#0078d4", color: "white", padding: "0.75rem 2rem" }}>
        <Link to="/" style={{ color: "white", textDecoration: "none", fontWeight: "bold", fontSize: "1.05rem" }}>
          Microsoft Learn 学習サポート
        </Link>
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
  );
}
