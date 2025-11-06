import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function SelectGuild() {
  const [guilds, setGuilds] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const guildsParam = params.get("guilds");

      // If no guild data from Discord callback, user isn’t logged in
      if (!guildsParam) {
        alert("⚠️ Please log in with Discord first.");
        navigate("/");
        return;
      }

      // Decode the guilds array from backend redirect
      const decodedGuilds = JSON.parse(decodeURIComponent(guildsParam));
      setGuilds(decodedGuilds);
    } catch (err) {
      console.error("Failed to load guilds:", err);
      alert("❌ Could not load Discord servers. Please log in again.");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  const handleSelectGuild = (guildId) => {
    // Go to dashboard for the selected server
    navigate(`/dashboard/${guildId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white text-xl">
        Loading your Discord servers...
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white px-6">
      <h1 className="text-3xl font-bold mb-6 text-center">
        Select a Discord Server
      </h1>

      {guilds.length === 0 ? (
        <p className="text-gray-400 text-lg">
          No servers found or missing permissions.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 w-full max-w-5xl">
          {guilds.map((guild) => (
            <button
              key={guild.id}
              onClick={() => handleSelectGuild(guild.id)}
              className="bg-blue-600 hover:bg-blue-700 py-4 px-6 rounded-xl transition flex flex-col items-center shadow-lg hover:shadow-blue-500/50"
            >
              {guild.icon ? (
                <img
                  src={`https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`}
                  alt={guild.name}
                  className="w-16 h-16 rounded-full mb-3 shadow-md"
                />
              ) : (
                <div className="w-16 h-16 bg-gray-800 rounded-full mb-3 flex items-center justify-center text-2xl">
                  🏠
                </div>
              )}
              <span className="truncate text-lg font-semibold">
                {guild.name}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
