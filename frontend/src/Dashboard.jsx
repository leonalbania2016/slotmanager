import { useParams } from "react-router-dom";

export default function Dashboard() {
  const { guildId } = useParams();

  return (
    <div className="h-screen bg-gray-900 text-white flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold mb-4">Dashboard</h1>
      <p className="text-lg">Guild ID: {guildId}</p>
      <p className="text-gray-400 mt-4">
        This is your dashboard for managing slots.
      </p>
    </div>
  );
}
