import { useEffect, useState } from "react";

export default function App() {
  const [guilds, setGuilds] = useState([]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (!token) return;

    fetch(`https://slotmanager-backend.onrender.com/api/decode?token=${token}`)
      .then(res => res.json())
      .then(data => setGuilds(data.guilds))
      .catch(err => console.error(err));
  }, []);

  const login = () => {
    window.location.href = "https://slotmanager-backend.onrender.com/auth/login";
  };

  if (!guilds.length) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-white">
        <h1 className="text-3xl mb-6 font-bold">Slot Manager</h1>
        <button
          onClick={login}
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
            className="bg-gray-800 p-4 rounded-lg flex items-center gap-3 hover:bg-gray-700 transition"
          >
            {g.icon && (
              <img
                src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`}
                alt=""
                className="w-10 h-10 rounded-full"
              />
            )}
            <span>{g.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
