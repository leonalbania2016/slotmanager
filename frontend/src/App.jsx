import React, { useEffect, useState } from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import Dashboard from "./Dashboard";
import SelectGuild from "./SelectGuild";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const CLIENT_ID = import.meta.env.VITE_DISCORD_CLIENT_ID;
const FRONTEND_URL = import.meta.env.VITE_FRONTEND_URL || "http://localhost:5173";
const REDIRECT_URI = import.meta.env.VITE_REDIRECT_URI || `${FRONTEND_URL}/`;

function Home() {
  const [guilds, setGuilds] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const session = params.get("session");

    if (session) {
      localStorage.setItem("discord_session", session);
      window.history.replaceState({}, document.title, "/");
    }

    const fetchGuilds = async () => {
      try {
        const token = localStorage.getItem("discord_session");
        if (!token) {
          setLoading(false);
          return;
        }

        const res = await fetch(`${API_URL}/api/decode?session=${token}`);
        if (!res.ok) throw new Error("Failed to fetch guilds");
        const data = await res.json();
        setGuilds(data.guilds || []);
      } catch (err) {
        console.error("❌ Guild fetch failed:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchGuilds();
  }, []);

  const loginWithDiscord = () => {
    const redirect = `https://discord.com/oauth2/authorize?client_id=${CLIENT_ID}&response_type=code&redirect_uri=${encodeURIComponent(
      REDIRECT_URI
    )}&scope=identify%20guilds`;
    window.location.href = redirect;
  };

  const handleSelectGuild = (guild_id) => {
    navigate(`/dashboard/${guild_id}`);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white">
      <h1 className="text-4xl font-bold mb-4">🎮 Slot Manager</h1>

      {loading ? (
        <p className="text-gray-400">Loading guilds...</p>
      ) : guilds.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-6">
          {guilds.map((g) => (
            <div
              key={g.id}
              onClick={() => handleSelectGuild(g.id)}
              className="bg-gray-800 hover:bg-gray-700 cursor-pointer p-4 rounded-lg text-center transition"
            >
              {g.icon ? (
                <img
                  src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`}
                  alt={g.name}
                  className="w-16 h-16 rounded-full mx-auto mb-2"
                />
              ) : (
                <div className="w-16 h-16 bg-gray-700 rounded-full mx-auto mb-2 flex items-center justify-center text-2xl">
                  🏠
                </div>
              )}
              <p className="truncate">{g.name}</p>
            </div>
          ))}
        </div>
      ) : (
        <button
          onClick={loginWithDiscord}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-lg font-semibold mt-4"
        >
          Login with Discord
        </button>
      )}
    </div>
  );
}

function DashboardWrapper() {
  const { guild_id } = useParams();
  return <Dashboard guild_id={guild_id} />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/dashboard/:guild_id" element={<DashboardWrapper />} />
      <Route path="/select-guild" element={<SelectGuild />} />
    </Routes>
  );
}
