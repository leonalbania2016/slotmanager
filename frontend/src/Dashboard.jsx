import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

export default function Dashboard() {
  const { guild_id } = useParams();
  const [slots, setSlots] = useState([]);
  const [saving, setSaving] = useState(false);

  // Load slots for this guild
  useEffect(() => {
    fetch(`https://slotmanager-backend.onrender.com/api/guilds/${guild_id}/slots`)
      .then((res) => res.json())
      .then((data) => setSlots(data))
      .catch((err) => console.error(err));
  }, [guild_id]);

  // Handle field changes
  const updateField = (slotNumber, field, value) => {
    setSlots((prev) =>
      prev.map((slot) =>
        slot.slot_number === slotNumber ? { ...slot, [field]: value } : slot
      )
    );
  };

  // Save slot settings
  const saveSlot = async (slot) => {
    setSaving(true);
    await fetch(
      `https://slotmanager-backend.onrender.com/api/guilds/${guild_id}/slots/${slot.slot_number}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(slot),
      }
    );
    setSaving(false);
    alert(`Slot #${slot.slot_number} saved ✅`);
  };

  // Upload background image
  const uploadBackground = async (slotNumber, file) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(
      `https://slotmanager-backend.onrender.com/api/guilds/${guild_id}/slots/${slotNumber}/background`,
      {
        method: "POST",
        body: formData,
      }
    );
    const data = await res.json();
    setSlots((prev) =>
      prev.map((slot) =>
        slot.slot_number === slotNumber
          ? { ...slot, background_url: data.background_url }
          : slot
      )
    );
  };

  return (
    <div className="p-10 text-white bg-gray-900 min-h-screen">
      <h1 className="text-3xl font-bold mb-6">
        Dashboard<br />
        <span className="text-gray-400 text-sm">Guild ID: {guild_id}</span>
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {slots.map((slot) => (
          <div
            key={slot.slot_number}
            className="bg-gray-800 p-4 rounded-xl shadow-md flex flex-col gap-3"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">
                #{slot.slot_number}{" "}
                <span className="text-gray-400 text-sm">
                  {slot.teamname || "Unassigned"}
                </span>
              </h2>
              {slot.background_url && (
                <img
                  src={slot.background_url}
                  alt="bg"
                  className="w-12 h-12 rounded-lg object-cover border"
                />
              )}
            </div>

            <input
              className="bg-gray-700 rounded px-3 py-2 text-sm"
              placeholder="Team name"
              value={slot.teamname}
              onChange={(e) =>
                updateField(slot.slot_number, "teamname", e.target.value)
              }
            />
            <input
              className="bg-gray-700 rounded px-3 py-2 text-sm"
              placeholder="Team tag"
              value={slot.teamtag}
              onChange={(e) =>
                updateField(slot.slot_number, "teamtag", e.target.value)
              }
            />
            <input
              className="bg-gray-700 rounded px-3 py-2 text-sm"
              placeholder="Emoji"
              value={slot.emoji}
              onChange={(e) =>
                updateField(slot.slot_number, "emoji", e.target.value)
              }
            />
            <div className="flex gap-2">
              <input
                className="bg-gray-700 rounded px-2 py-1 text-sm flex-1"
                placeholder="Font family"
                value={slot.font_family}
                onChange={(e) =>
                  updateField(slot.slot_number, "font_family", e.target.value)
                }
              />
              <input
                type="color"
                className="w-10 h-10 border-0"
                value={slot.font_color}
                onChange={(e) =>
                  updateField(slot.slot_number, "font_color", e.target.value)
                }
              />
            </div>

            {/* Upload background */}
            <label className="bg-gray-700 text-center py-2 rounded cursor-pointer hover:bg-gray-600 transition">
              Upload Background
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) =>
                  uploadBackground(slot.slot_number, e.target.files[0])
                }
              />
            </label>

            <button
              onClick={() => saveSlot(slot)}
              className="bg-indigo-600 px-4 py-2 rounded hover:bg-indigo-500 transition"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
