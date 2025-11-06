import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import SelectGuild from "./SelectGuild";
import Dashboard from "./Dashboard";

// Simple layout wrapper for global styling
const Layout = ({ children }) => (
  <div
    style={{
      minHeight: "100vh",
      backgroundColor: "#0d1117",
      color: "white",
      fontFamily: "Inter, Arial, sans-serif",
      padding: "20px",
    }}
  >
    {children}
  </div>
);

// 404 fallback
const NotFound = () => (
  <div
    style={{
      textAlign: "center",
      marginTop: "100px",
    }}
  >
    <h1>404 - Page Not Found</h1>
    <p>The page you are looking for doesn’t exist.</p>
    <a href="/" style={{ color: "#5865F2", textDecoration: "none" }}>
      Go back home
    </a>
  </div>
);

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          {/* Default route: Login and guild selection */}
          <Route path="/" element={<SelectGuild />} />

          {/* Dashboard (guild_id comes from query param like ?guild_id=123) */}
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Old route redirect (optional) */}
          <Route path="/select-guild" element={<Navigate to="/" replace />} />

          {/* Fallback 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
