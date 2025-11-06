import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function SelectGuild() {
  const [guilds, setGuilds] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchGuilds = async () => {
      try {
        const token = localStorage.getItem("discord_session");
        if (!token) {
          alert("⚠️ Please log in with Discord first.");
          navigate("/");
          return;
        }

        const res = await fetch(`${API_URL}/api/decode?session=${token}`);
        if (!res.ok) throw new Error("Failed to load guilds");
        const data = await res.json();
        setGuilds(data.guilds || []);
      } catch (err) {
        console.error(err);
        alert("❌ Could not load Discord guilds.");
      } finally {
        setLoading(false);
      }
    };

    fetchGuilds();
  }, [navigate]);

  const handleSelectGuild = (guild_id) => {
    navigate(`/dashboard/${guild_id}`);
  };

  if (loading)
    return (
      <div className="text-center p-10 text-gray-400">
        Loading your Discord servers...
      </div>
    );

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white">
      <h1 className="text-3xl font-bold mb-6">Select a Discord Server</h1>
      {guilds.length === 0 ? (
        <p className="text-gray-400">No servers found or permissions missing.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 w-full max-w-4xl">
          {guilds.map((g) => (
            <button
              key={g.id}
              onClick={() => handleSelectGuild(g.id)}
              className="bg-blue-600 hover:bg-blue-700 py-4 px-6 rounded-xl transition flex flex-col items-center shadow-md"
            >
              {g.icon ? (
                <img
                  src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`}
                  alt={g.name}
                  className="w-16 h-16 rounded-full mb-3 shadow-lg"
                />
              ) : (
                <div className="w-16 h-16 bg-gray-800 rounded-full mb-3 flex items-center justify-center text-2xl">
                  🏠
                </div>
              )}
              <span className="truncate text-lg font-semibold">{g.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
