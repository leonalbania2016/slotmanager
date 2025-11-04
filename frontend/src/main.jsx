import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App";
import Dashboard from "./Dashboard";
import "./index.css";

// ✅ Restored old guild-based routing
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Main landing and login */}
        <Route path="/*" element={<App />} />

        {/* Dashboard now expects a guild_id param again */}
        <Route path="/dashboard/:guild_id" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
