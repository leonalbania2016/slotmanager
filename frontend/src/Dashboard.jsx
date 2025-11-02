import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";

export default function Dashboard() {
  const { id } = useParams();
  const [slots, setSlots] = useState([]);

  useEffect(() => {
    fetch(`https://slotmanager-backend.onrender.com/api/guilds/${id}/slots`)
      .then(res => res.json())
      .then(data => setSlots(data))
      .catch(err => console.error("Error fetching slots:", err));
  }, [id]);

  return (
    <div className="p-8 bg-gray-900 min-h-screen text-white">
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      <p className="mb-4 text-gray-400">Guild ID: {id}</p>
      <h2 className="text-2xl mb-4">Slots</h2>

      {slots.length === 0 ? (
        <p>No slots found for this server.</p>
      ) : (
        <div className="grid gap-4">
          {slots.map((slot, i) => (
            <div
              key={i}
              className="bg-gray-800 p-4 rounded-lg flex justify-between items-center hover:bg-gray-700 transition"
            >
              <div>
                <p className="font-semibold text-lg">
                  #{slot.slot_number} {slot.teamname || "Unassigned"}
                </p>
                {slot.teamtag && (
                  <p className="text-sm text-gray-400">Tag: {slot.teamtag}</p>
                )}
              </div>
              {slot.emoji && (
                <span className="text-2xl">{slot.emoji}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
