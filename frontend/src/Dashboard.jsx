import React, { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Dashboard({ guild_id }) {
  const [slots, setSlots] = useState([]);
  const [emojis, setEmojis] = useState([]);
  const [backgrounds, setBackgrounds] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  // Fetch initial data
  useEffect(() => {
    if (!guild_id) return;

    const fetchAll = async () => {
      try {
        setLoading(true);

        const [slotsRes, gifsRes, channelsRes, emojisRes] = await Promise.all([
          fetch(`${API_URL}/api/guilds/${guild_id}/slots`),
          fetch(`${API_URL}/api/guilds/${guild_id}/gifs`),
          fetch(`${API_URL}/api/guilds/${guild_id}/channels`),
          fetch(`${API_URL}/api/guilds/${guild_id}/emojis`),
        ]);

        const [slotsData, gifsData, channelsData, emojisData] = await Promise.all([
          slotsRes.json(),
          gifsRes.json(),
          channelsRes.json(),
          emojisRes.json(),
        ]);

        // ✅ Normalize responses so they're always arrays
        setSlots(Array.isArray(slotsData) ? slotsData : slotsData.slots || []);
        setBackgrounds(Array.isArray(gifsData) ? gifsData : gifsData.gifs || []);
        setChannels(Array.isArray(channelsData) ? channelsData : channelsData.channels || []);
        setEmojis(Array.isArray(emojisData) ? emojisData : emojisData.emojis || []);
      } catch (err) {
        console.error("❌ Failed to load dashboard data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [guild_id]);

  // Update a single slot field
  const updateSlot = (index, field, value) => {
    const updated = [...slots];
    updated[index][field] = value;
    setSlots(updated);
  };

  // Save all slots in one request
  const saveAllSlots = async () => {
    if (!selectedChannel) {
      alert("⚠️ Please select a Discord channel first!");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/guilds/${guild_id}/slots/bulk_update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slots }),
      });

      if (!res.ok) throw new Error("Bulk save failed");
      alert("✅ All slots saved successfully!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to save all slots.");
    } finally {
      setSaving(false);
    }
  };

  // Send all slots to Discord
  const sendAllSlots = async () => {
    if (!selectedChannel) {
      alert("⚠️ Please select a Discord channel first!");
      return;
    }

    setSending(true);
    try {
      const res = await fetch(`${API_URL}/api/guilds/${guild_id}/send_slots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel_id: selectedChannel }),
      });

      if (!res.ok) throw new Error("Send failed");
      alert("✅ Slots sent to Discord!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to send slots.");
    } finally {
      setSending(false);
    }
  };

  if (loading)
    return <div className="text-center p-10 text-gray-400">Loading...</div>;

  return (
    <div className="max-w-6xl mx-auto p-6 text-white">
      <h1 className="text-3xl font-bold mb-4">🎮 Slot Manager Dashboard</h1>

      {/* Channel Selector */}
      <div className="mb-4">
        <label className="block mb-2 text-gray-400">Select Discord Channel</label>
        <select
          value={selectedChannel}
          onChange={(e) => setSelectedChannel(e.target.value)}
          className="bg-gray-800 text-white p-2 rounded w-full"
        >
          <option value="">-- Choose a Channel --</option>
          {Array.isArray(channels) &&
            channels.map((ch) => (
              <option key={ch.id} value={ch.id}>
                #{ch.name}
              </option>
            ))}
        </select>
      </div>

      {/* Global Buttons */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={saveAllSlots}
          disabled={saving}
          className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded transition w-1/2"
        >
          {saving ? "💾 Saving All..." : "💾 Save All Slots"}
        </button>

        <button
          onClick={sendAllSlots}
          disabled={sending}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition w-1/2"
        >
          {sending ? "📤 Sending..." : "📤 Send Slots to Discord"}
        </button>
      </div>

      {/* Slots Editor */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {Array.isArray(slots) &&
          slots.map((slot, index) => (
            <div
              key={slot.slot_number || index}
              className="bg-gray-900 p-4 rounded-xl border border-gray-700 shadow-md"
            >
              <h2 className="text-xl font-semibold mb-2">
                Slot #{slot.slot_number}
              </h2>

              <input
                type="text"
                placeholder="Team Name"
                value={slot.teamname || ""}
                onChange={(e) => updateSlot(index, "teamname", e.target.value)}
                className="w-full p-2 mb-2 bg-gray-800 rounded text-white"
              />

              <input
                type="text"
                placeholder="Team Tag"
                value={slot.teamtag || ""}
                onChange={(e) => updateSlot(index, "teamtag", e.target.value)}
                className="w-full p-2 mb-2 bg-gray-800 rounded text-white"
              />

              {/* Emoji Picker */}
              <select
                value={slot.emoji || ""}
                onChange={(e) => updateSlot(index, "emoji", e.target.value)}
                className="w-full p-2 mb-2 bg-gray-800 rounded text-white"
              >
                <option value="">-- Choose Emoji --</option>
                {Array.isArray(emojis) &&
                  emojis.map((em) => (
                    <option key={em.id || em.name} value={em.format || em.name}>
                      {em.name}
                    </option>
                  ))}
              </select>

              {/* Background Selector */}
              <select
                value={slot.background_url || ""}
                onChange={(e) => updateSlot(index, "background_url", e.target.value)}
                className="w-full p-2 mb-2 bg-gray-800 rounded text-white"
              >
                <option value="">-- Choose Background --</option>
                {Array.isArray(backgrounds) &&
                  backgrounds.map((bg, i) => (
                    <option key={i} value={bg.url || bg}>
                      {bg.name || bg}
                    </option>
                  ))}
              </select>

              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="Font Size"
                  value={slot.font_size || 48}
                  onChange={(e) =>
                    updateSlot(index, "font_size", parseInt(e.target.value))
                  }
                  className="w-1/3 p-2 bg-gray-800 rounded text-white"
                />
                <input
                  type="color"
                  value={slot.font_color || "#FFFFFF"}
                  onChange={(e) => updateSlot(index, "font_color", e.target.value)}
                  className="w-1/3 h-10 rounded"
                />
                <input
                  type="number"
                  placeholder="Padding Top"
                  value={slot.padding_top || 0}
                  onChange={(e) =>
                    updateSlot(index, "padding_top", parseInt(e.target.value))
                  }
                  className="w-1/3 p-2 bg-gray-800 rounded text-white"
                />
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}
