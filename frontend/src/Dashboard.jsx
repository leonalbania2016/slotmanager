import React, { useEffect, useState } from "react";
import axios from "axios";

const backendURL = "https://slotmanager-backend.onrender.com";

const Dashboard = () => {
  const [guildId, setGuildId] = useState(null);
  const [slots, setSlots] = useState([]);
  const [emojis, setEmojis] = useState([]);
  const [gifs, setGifs] = useState([]);
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");

  // ------------------------------
  // Load guild ID from URL (query)
  // ------------------------------
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("guild_id");
    if (id) {
      setGuildId(id);
    }
  }, []);

  // ------------------------------
  // Fetch initial data when guildId is available
  // ------------------------------
  useEffect(() => {
    if (!guildId) return;

    const fetchAll = async () => {
      try {
        setLoading(true);

        const [slotsRes, emojisRes, gifsRes, channelsRes] = await Promise.all([
          axios.get(`${backendURL}/api/guilds/${guildId}/slots`),
          axios.get(`${backendURL}/api/guilds/${guildId}/emojis`),
          axios.get(`${backendURL}/api/guilds/${guildId}/gifs`),
          axios.get(`${backendURL}/api/guilds/${guildId}/channels`),
        ]);

        setSlots(slotsRes.data.slots || []);
        setEmojis(emojisRes.data.emojis || []);
        setGifs(gifsRes.data.gifs || []);
        setChannels(channelsRes.data.channels || []);
      } catch (err) {
        console.error("❌ Failed to fetch initial data:", err);
        alert("Failed to load data from backend.");
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [guildId]);

  // ------------------------------
  // Update individual slot field
  // ------------------------------
  const updateSlot = (index, field, value) => {
    const newSlots = [...slots];
    newSlots[index][field] = value;
    setSlots(newSlots);
  };

  // ------------------------------
  // Add new slot row
  // ------------------------------
  const addSlot = () => {
    const newSlot = {
      slot_number: slots.length + 1,
      teamname: "",
      teamtag: "",
      emoji: "",
      background_name: "default.gif",
      font_family: "DejaVuSans.ttf",
      font_size: 64,
      font_color: "#FFFFFF",
      padding_top: 0,
      padding_bottom: 0,
    };
    setSlots([...slots, newSlot]);
  };

  // ------------------------------
  // Save All Slots to Backend
  // ------------------------------
  const saveAllSlots = async () => {
    if (!guildId) return alert("Guild not selected!");

    try {
      setLoading(true);
      setSaveStatus("Saving slots...");

      // Ensure slot_number is always numeric
      const formattedSlots = slots.map((slot, index) => ({
        ...slot,
        slot_number: Number(slot.slot_number || index + 1),
      }));

      const response = await axios.post(
        `${backendURL}/api/guilds/${guildId}/slots/bulk_update`,
        { slots: formattedSlots },
        { headers: { "Content-Type": "application/json" } }
      );

      console.log("✅ Backend response:", response.data);
      setSaveStatus("✅ Slots saved successfully!");
    } catch (err) {
      console.error("❌ Save failed:", err.response?.data || err);
      setSaveStatus("❌ Failed to save all slots. Check console for details.");
    } finally {
      setLoading(false);
      setTimeout(() => setSaveStatus(""), 5000);
    }
  };

  // ------------------------------
  // Send Slots to a Channel
  // ------------------------------
  const sendSlots = async () => {
    if (!guildId || !selectedChannel)
      return alert("Please select a channel first!");

    try {
      setLoading(true);
      setSaveStatus("Sending slots to Discord...");

      const response = await axios.post(
        `${backendURL}/api/guilds/${guildId}/send_slots`,
        { channel_id: selectedChannel },
        { headers: { "Content-Type": "application/json" } }
      );

      console.log("📤 Sent:", response.data);
      setSaveStatus("✅ Slots sent successfully!");
    } catch (err) {
      console.error("❌ Send failed:", err.response?.data || err);
      setSaveStatus("❌ Failed to send slots.");
    } finally {
      setLoading(false);
      setTimeout(() => setSaveStatus(""), 5000);
    }
  };

  // ------------------------------
  // Render UI
  // ------------------------------
  if (loading && slots.length === 0) {
    return <div className="loading">Loading guild data...</div>;
  }

  return (
    <div className="dashboard">
      <h1>🎮 Slot Manager Dashboard</h1>

      {/* Save Status */}
      {saveStatus && <div className="status">{saveStatus}</div>}

      {/* Channel Selector */}
      <div className="channel-selector">
        <label>Send to Channel:</label>
        <select
          value={selectedChannel}
          onChange={(e) => setSelectedChannel(e.target.value)}
        >
          <option value="">Select channel...</option>
          {channels.map((c) => (
            <option key={c.id} value={c.id}>
              #{c.name}
            </option>
          ))}
        </select>
        <button onClick={sendSlots} disabled={!selectedChannel || loading}>
          🚀 Send Slots
        </button>
      </div>

      {/* Slots Table */}
      <table className="slots-table">
        <thead>
          <tr>
            <th>Slot #</th>
            <th>Team Name</th>
            <th>Tag</th>
            <th>Emoji</th>
            <th>Background</th>
            <th>Font</th>
            <th>Size</th>
            <th>Color</th>
            <th>Padding Top</th>
            <th>Padding Bottom</th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot, index) => (
            <tr key={index}>
              <td>{slot.slot_number}</td>
              <td>
                <input
                  value={slot.teamname}
                  onChange={(e) =>
                    updateSlot(index, "teamname", e.target.value)
                  }
                />
              </td>
              <td>
                <input
                  value={slot.teamtag}
                  onChange={(e) =>
                    updateSlot(index, "teamtag", e.target.value)
                  }
                />
              </td>
              <td>
                <select
                  value={slot.emoji}
                  onChange={(e) => updateSlot(index, "emoji", e.target.value)}
                >
                  <option value="">None</option>
                  {emojis.map((em, i) => (
                    <option key={i} value={em.name}>
                      {em.name}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <select
                  value={slot.background_name}
                  onChange={(e) =>
                    updateSlot(index, "background_name", e.target.value)
                  }
                >
                  {gifs.map((g, i) => (
                    <option key={i} value={g.name}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  value={slot.font_family}
                  onChange={(e) =>
                    updateSlot(index, "font_family", e.target.value)
                  }
                />
              </td>
              <td>
                <input
                  type="number"
                  value={slot.font_size}
                  onChange={(e) =>
                    updateSlot(index, "font_size", Number(e.target.value))
                  }
                  style={{ width: "70px" }}
                />
              </td>
              <td>
                <input
                  type="color"
                  value={slot.font_color}
                  onChange={(e) =>
                    updateSlot(index, "font_color", e.target.value)
                  }
                />
              </td>
              <td>
                <input
                  type="number"
                  value={slot.padding_top}
                  onChange={(e) =>
                    updateSlot(index, "padding_top", Number(e.target.value))
                  }
                  style={{ width: "70px" }}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={slot.padding_bottom}
                  onChange={(e) =>
                    updateSlot(index, "padding_bottom", Number(e.target.value))
                  }
                  style={{ width: "70px" }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Buttons */}
      <div className="buttons">
        <button onClick={addSlot}>➕ Add Slot</button>
        <button onClick={saveAllSlots}>💾 Save All Slots</button>
      </div>
    </div>
  );
};

export default Dashboard;
