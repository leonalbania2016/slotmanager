import { useSearchParams, useNavigate } from "react-router-dom";

export default function SelectGuild() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const username = params.get("username");
  const user_id = params.get("user_id");
  const guilds = JSON.parse(params.get("guilds") || "[]");

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white">
      <h1 className="text-3xl font-bold mb-6">Welcome, {username}!</h1>
      <p className="text-gray-400 mb-4">Choose a server to manage:</p>
      <div className="grid grid-cols-1 gap-3 w-full max-w-sm">
        {guilds.map((g) => (
          <button
            key={g.id}
            onClick={() =>
              navigate(`/dashboard/${g.id}?user_id=${user_id}&username=${username}`)
            }
            className="bg-blue-600 hover:bg-blue-700 py-3 px-4 rounded-lg transition"
          >
            {g.name}
          </button>
        ))}
      </div>
    </div>
  );
}
