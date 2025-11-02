import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App";
import Dashboard from "./Dashboard";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<App />} />   {/* 👈 note the trailing "/*" */}
        <Route path="/dashboard/:guild_id" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
