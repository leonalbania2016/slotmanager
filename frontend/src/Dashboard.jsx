import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

export default function Dashboard() {
  const { guild_id } = useParams();
  const [slots, setSlots] = useState([]);
  const [backgroundUrl, setBackgroundUrl] = useState("");
  const [channelId, setChannelId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`https://slotmanager-backend.onrender.com/api/guilds/${guild_id}/slots`)
      .then(res => res.json())
      .then(data => {
        setSlots(data);
        if (data.length > 0 && data[0].background_url) {
          setBackgroundUrl(data[0].background_url);
        }
      })
      .catch(err => console.error("Error loading slots:", err));
  }, [guild_id]);

  const updateSlot = (index, key, value) => {
    const updated = [...slots];
    updated[index][key] = value;
    setSlots(updated);
  };

  const saveSlot = async (slot) => {
    setSaving(true);
    try {
      const res = await fetch(
        `https://slotmanager-backend.onrender.com/api/guilds/${guild_id}/slots/${slot.slot_number}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            teamname: slot.teamname,
            teamtag: slot.teamtag,
            emoji: slot.emoji,
            background_url: backgroundUrl,
            channel_id: channelId,
          }),
        }
      );
      if (!res.ok) throw new Error("Save failed");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to save slot");
    } finally {
      setSaving(false);
    }
  };

  const saveAll = async () => {
    for (const slot of slots) {
      await saveSlot(slot);
    }
    alert("✅ All slots saved successfully!");
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
      <p className="mb-6 text-gray-400">Guild ID: {guild_id}</p>

      <div className="mb-8 bg-gray-800 p-4 rounded-lg">
        <h2 className="text-xl font-semibold mb-2">Global Settings</h2>
        <input
          className="w-full bg-gray-700 p-2 rounded mb-3"
          placeholder="Background GIF URL"
          value={backgroundUrl}
          onChange={(e) => setBackgroundUrl(e.target.value)}
        />
        <input
          className="w-full bg-gray-700 p-2 rounded"
          placeholder="Discord Channel ID to send slots"
          value={channelId}
          onChange={(e) => setChannelId(e.target.value)}
        />
      </div>

      <h2 className="text-xl mb-4 font-semibold">Slots</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {slots.map((slot, index) => (
          <div
            key={slot.slot_number}
            className="bg-gray-800 p-4 rounded-lg shadow hover:bg-gray-700 transition"
          >
            <h3 className="font-semibold text-lg mb-2">
              #{slot.slot_number}{" "}
              <span className="text-sm text-gray-400">
                {slot.teamname || "Unassigned"}
              </span>
            </h3>

            <input
              className="w-full bg-gray-700 rounded p-2 mb-2"
              placeholder="Team Name"
              value={slot.teamname || ""}
              onChange={(e) => updateSlot(index, "teamname", e.target.value)}
            />
            <input
              className="w-full bg-gray-700 rounded p-2 mb-2"
              placeholder="Team Tag"
              value={slot.teamtag || ""}
              onChange={(e) => updateSlot(index, "teamtag", e.target.value)}
            />

            <select
              className="w-full bg-gray-700 rounded p-2 mb-2"
              value={slot.emoji || ""}
              onChange={(e) => updateSlot(index, "emoji", e.target.value)}
            >
              <option value="">Select Emoji</option>
              <option value="✅">✅ Yes</option>
              <option value="❌">❌ No</option>
            </select>

            <button
              onClick={() => saveSlot(slot)}
              disabled={saving}
              className="bg-indigo-600 px-4 py-2 rounded mt-2 w-full hover:bg-indigo-500 transition"
            >
              {saving ? "Saving..." : "Save Slot"}
            </button>
          </div>
        ))}
      </div>

      <button
        onClick={saveAll}
        disabled={saving}
        className="mt-8 bg-green-600 px-6 py-3 rounded-lg hover:bg-green-500 transition"
      >
        {saving ? "Saving..." : "Save All Slots"}
      </button>
    </div>
  );
}
