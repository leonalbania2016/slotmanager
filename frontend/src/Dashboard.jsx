import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

export default function Dashboard() {
  const { guild_id } = useParams();
  const [slots, setSlots] = useState([]);
  const [backgroundUrl, setBackgroundUrl] = useState("");
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [saving, setSaving] = useState(false);

  const API_URL = "https://slotmanager-backend.onrender.com";

  console.log("Dashboard loaded for guild:", guild_id);

 // Fetch slots for this guild
useEffect(() => {
  if (!guild_id) return;
  fetch(`${API_URL}/api/guilds/${guild_id}/slots`)
    .then((res) => res.json())
    .then((data) => {
      setSlots(data);
      if (data.length > 0 && data[0].background_url) {
        setBackgroundUrl(data[0].background_url);
      }
    })
    .catch((err) => console.error("Error loading slots:", err));
}, [guild_id]);

// Fetch all channels for this guild
useEffect(() => {
  if (!guild_id) return;
  fetch(`${API_URL}/api/guilds/${guild_id}/channels`)
    .then((res) => res.json())
    .then((data) => {
      console.log("Fetched channels:", data); // 👈 logs what backend returns
      if (Array.isArray(data)) {
        // backend returns a plain list like [{id, name}, ...]
        setChannels(data);
      } else if (data.channels && Array.isArray(data.channels)) {
        // or if it’s wrapped like { channels: [...] }
        setChannels(data.channels);
      } else {
        console.warn("Unexpected channels response:", data);
      }
    })
    .catch((err) => console.error("Failed to load channels:", err));
}, [guild_id]);


  // Update slot values locally
  const updateSlot = (index, key, value) => {
    const updated = [...slots];
    updated[index][key] = value;
    setSlots(updated);
  };

  // Save single slot to backend
  const saveSlot = async (slot) => {
    if (!selectedChannel) {
      alert("Please select a Discord channel first!");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(
        `${API_URL}/api/guilds/${guild_id}/slots/${slot.slot_number}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            teamname: slot.teamname,
            teamtag: slot.teamtag,
            emoji: slot.emoji,
            background_url: backgroundUrl,
            channel_id: selectedChannel,
          }),
        }
      );

      if (!res.ok) throw new Error("Save failed");
      console.log(`Slot #${slot.slot_number} saved successfully.`);
    } catch (err) {
      console.error(err);
      alert("❌ Failed to save slot");
    } finally {
      setSaving(false);
    }
  };

  // Save all slots
  const saveAll = async () => {
    if (!selectedChannel) {
      alert("Please select a Discord channel first!");
      return;
    }

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

        {/* Background URL (applies to all slots) */}
        <input
          className="w-full bg-gray-700 p-2 rounded mb-3"
          placeholder="Background GIF URL (applies to all slots)"
          value={backgroundUrl}
          onChange={(e) => setBackgroundUrl(e.target.value)}
        />

        {/* Channel Dropdown */}
        <div className="mb-3">
          <label className="block mb-2 font-semibold">
            Select Discord Channel:
          </label>
          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="bg-gray-700 p-2 rounded w-full"
          >
            <option value="">-- Choose a channel --</option>
            {channels.map((ch) => (
              <option key={ch.id} value={ch.id}>
                #{ch.name}
              </option>
            ))}
          </select>
          <button
  onClick={() => {
    if (!selectedChannel) return alert("Please select a channel first!");
    fetch(`${API_URL}/api/guilds/${guild_id}/send_slots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_id: selectedChannel }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "sent") alert("✅ Slots sent successfully!");
        else alert("❌ Failed to send slots.");
      })
      .catch((err) => {
        console.error("Failed to send slots:", err);
        alert("❌ Error sending slots.");
      });
  }}
  className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded mt-2"
>
  📤 Send Slots to Discord
</button>

        </div>
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

            {/* Emoji dropdown (Yes / No only) */}
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
