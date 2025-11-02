import { useEffect, useState } from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import Dashboard from "./Dashboard";

function Home() {
  const [guilds, setGuilds] = useState([]);
  const [loading, setLoading] = useState(true);

  const API_URL = import.meta.env.VITE_API_URL || "https://slotmanager-backend.onrender.com";
  const CLIENT_ID = import.meta.env.VITE_DISCORD_CLIENT_ID || "1432457167306227885";
  const REDIRECT_URI = import.meta.env.VITE_REDIRECT_URI || `${API_URL}/auth/callback`;

  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const session = params.get("session");

    if (!session) {
      setLoading(false);
      return;
    }

    fetch(`${API_URL}/api/decode?session=${session}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to decode session");
        return res.json();
      })
      .then((data) => {
        if (data.guilds) setGuilds(data.guilds);
      })
      .catch((err) => console.error("Decode error:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleLogin = () => {
    const params = new URLSearchParams({
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      response_type: "code",
      scope: "identify guilds",
    });
    window.location.href = `https://discord.com/oauth2/authorize?${params.toString()}`;
  };

  const handleSelectGuild = (guildId) => {
    // ✅ Use React Router navigation instead of manual redirect
    navigate(`/dashboard/${guildId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900 text-white">
        <p className="text-lg animate-pulse">Loading...</p>
      </div>
    );
  }

  if (!guilds.length) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-white">
        <h1 className="text-3xl mb-6 font-bold">Slot Manager</h1>
        <button
          onClick={handleLogin}
          className="bg-indigo-600 px-6 py-3 rounded-lg text-lg hover:bg-indigo-500 transition"
        >
          Login with Discord
        </button>
      </div>
    );
  }

  return (
    <div className="p-10 text-white bg-gray-900 min-h-screen">
      <h1 className="text-3xl font-bold mb-6">Select a Server</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {guilds.map((g) => (
          <div
            key={g.id}
            onClick={() => handleSelectGuild(g.id)}
            className="bg-gray-800 p-4 rounded-lg flex items-center gap-3 hover:bg-indigo-600 cursor-pointer transition"
          >
            {g.icon ? (
              <img
                src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`}
                alt={g.name}
                className="w-10 h-10 rounded-full"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-gray-400">
                ?
              </div>
            )}
            <span className="text-lg">{g.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/dashboard/:guild_id" element={<Dashboard />} />
    </Routes>
  );
}
