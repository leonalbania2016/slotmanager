import { useEffect, useState } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";

// helper for parsing ?user_id=...&username=...
function useQuery() {
  return new URLSearchParams(useLocation().search);
}

export default function Dashboard() {
  const { guild_id } = useParams();
  const [slots, setSlots] = useState([]);
  const [backgroundUrl, setBackgroundUrl] = useState("");
  const [channels, setChannels] = useState([]);
  const [gifs, setGifs] = useState([]);
  const [selectedGif, setSelectedGif] = useState("");
  const [selectedChannel, setSelectedChannel] = useState("");
  const [saving, setSaving] = useState(false);

  const API_URL = "https://slotmanager-backend.onrender.com";
  const query = useQuery();
  const navigate = useNavigate();

  // 🧩 Handle login redirect from Discord
  useEffect(() => {
    const userId = query.get("user_id");
    const username = query.get("username");

    if (userId && username) {
      console.log("✅ Logged in as:", username);
      localStorage.setItem("user_id", userId);
      localStorage.setItem("username", username);
      // Clean up the URL
      navigate("/dashboard", { replace: true });
    }
  }, []);

  // 🧠 Redirect to login if not logged in
  useEffect(() => {
    const userId = localStorage.getItem("user_id");
    if (!userId) {
      navigate("/login");
    }
  }, []);

  // 🎯 Load slots
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

  // 💬 Load channels
  useEffect(() => {
    if (!guild_id) return;
    fetch(`${API_URL}/api/guilds/${guild_id}/channels`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setChannels(data);
        else if (data.channels && Array.isArray(data.channels))
          setChannels(data.channels);
      })
      .catch((err) => console.error("Failed to load channels:", err));
  }, [guild_id]);

  // 🎞️ Load available GIFs
  useEffect(() => {
    fetch(`${API_URL}/api/gifs`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data.gifs)) setGifs(data.gifs);
      })
      .catch((err) => console.error("Error loading GIFs:", err));
  }, []);

  // ✏️ Update slot locally
  const updateSlot = (index, key, value) => {
    const updated = [...slots];
    updated[index][key] = value;
    setSlots(updated);
  };

  // 💾 Save one slot
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
      console.log(`✅ Slot #${slot.slot_number} saved successfully.`);
    } catch (err) {
      console.error(err);
      alert("❌ Failed to save slot");
    } finally {
      setSaving(false);
    }
  };

  // 🚀 Send all slots to Discord
  const sendSlots = async () => {
    if (!selectedChannel) {
      alert("⚠️ Please select a Discord channel first!");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/guilds/${guild_id}/send_slots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel_id: selectedChannel,
          gif_name: selectedGif || "default.gif",
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        console.error("Backend error:", errorText);
        alert("❌ Failed to send slots — check backend logs.");
        return;
      }

      const data = await res.json();
      if (data.status === "sent" || data.status === "success") {
        alert("✅ Slots sent successfully!");
      } else {
        alert("❌ Failed to send slots.");
      }
    } catch (err) {
      console.error("Failed to send slots:", err);
      alert("❌ Network error while sending slots.");
    }
  };

  // 🧭 Logged-in user display
  const username = localStorage.getItem("username") || "Guest";

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-3xl font-bold mb-2 text-left">Dashboard</h1>
      <p className="mb-6 text-gray-400 text-left">
        Welcome, <span className="font-semibold">{username}</span> 👋
      </p>
      <p className="mb-6 text-gray-400 text-left">Guild ID: {guild_id}</p>

      {/* 🌍 Global Controls */}
      <div className="mb-8 bg-gray-800 p-4 rounded-lg">
        <h2 className="text-xl font-semibold mb-2">Global Settings</h2>

        {/* GIF Selector */}
        <div className="mb-4">
          <label className="block mb-2 font-semibold text-left">
            Select Background GIF:
          </label>
          <select
            value={selectedGif}
            onChange={(e) => setSelectedGif(e.target.value)}
            className="bg-gray-700 p-2 rounded w-full"
          >
            <option value="">-- Choose a GIF (default if empty) --</option>
            {gifs.map((gif) => (
              <option key={gif} value={gif}>
                {gif}
              </option>
            ))}
          </select>
        </div>

        {/* Channel Selector */}
        <div className="mb-3">
          <label className="block mb-2 font-semibold text-left">
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
            onClick={sendSlots}
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded mt-3 transition w-full"
          >
            📤 Send Slots to Discord
          </button>
        </div>
      </div>

      {/* 🧩 Slot List */}
      <h2 className="text-xl mb-4 font-semibold text-left">Slots</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {slots.map((slot, index) => (
          <div
            key={slot.slot_number}
            className="bg-gray-800 p-4 rounded-lg shadow hover:bg-gray-700 transition text-left"
          >
            <h3 className="text-lg font-bold mb-2 text-left">
              {slot.slot_number}{" "}
              <span className="text-sm text-gray-400">
                {slot.teamname || "FreeSlot"} {slot.teamtag || ""}
              </span>
            </h3>

            <input
              className="w-full bg-gray-700 rounded p-2 mb-2 text-left"
              placeholder="Team Name"
              value={slot.teamname || ""}
              onChange={(e) => updateSlot(index, "teamname", e.target.value)}
            />
            <input
              className="w-full bg-gray-700 rounded p-2 mb-2 text-left"
              placeholder="Team Tag"
              value={slot.teamtag || ""}
              onChange={(e) => updateSlot(index, "teamtag", e.target.value)}
            />

            <select
              className="w-full bg-gray-700 rounded p-2 mb-2 text-left"
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
              className="bg-blue-600 px-4 py-2 rounded mt-2 w-full hover:bg-blue-500 transition"
            >
              {saving ? "Saving..." : "Save Slot"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
