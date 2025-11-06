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

  // ------------------------------------------
  // Load guild ID from URL
  // ------------------------------------------
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("guild_id");
    if (id) setGuildId(id);
  }, []);

  // ------------------------------------------
  // Fetch guild data
  // ------------------------------------------
  useEffect(() => {
    if (!guildId) return;

    const fetchData = async () => {
      try {
        setLoading(true);
        const [slotsRes, gifsRes, emojisRes, channelsRes] = await Promise.all([
          axios.get(`${backendURL}/api/guilds/${guildId}/slots`),
          axios.get(`${backendURL}/api/guilds/${guildId}/gifs`),
          axios.get(`${backendURL}/api/guilds/${guildId}/emojis`),
          axios.get(`${backendURL}/api/guilds/${guildId}/channels`),
        ]);

        // ✅ backend returns arrays directly
        setSlots(slotsRes.data || []);
        setGifs(gifsRes.data || []);
        setEmojis(emojisRes.data || []);
        setChannels(channelsRes.data || []);
      } catch (error) {
        console.error("❌ Error fetching data:", error);
        alert("Failed to load data. Check console for details.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [guildId]);

  // ------------------------------------------
  // Slot handlers
  // ------------------------------------------
  const updateSlot = (index, field, value) => {
    const newSlots = [...slots];
    newSlots[index][field] = value;
    setSlots(newSlots);
  };

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

  // ------------------------------------------
  // Save all slots
  // ------------------------------------------
  const saveAllSlots = async () => {
    if (!guildId) return alert("Guild not selected!");

    try {
      setLoading(true);
      setSaveStatus("💾 Saving slots...");

      const formattedSlots = slots.map((slot, index) => ({
        ...slot,
        slot_number: Number(slot.slot_number || index + 1),
      }));

      const res = await axios.post(
        `${backendURL}/api/guilds/${guildId}/slots/bulk_update`,
        { slots: formattedSlots },
        { headers: { "Content-Type": "application/json" } }
      );

      console.log("✅ Saved:", res.data);
      setSaveStatus("✅ Slots saved successfully!");
    } catch (err) {
      console.error("❌ Save failed:", err.response?.data || err);
      setSaveStatus("❌ Failed to save all slots. Check console for details.");
    } finally {
      setLoading(false);
      setTimeout(() => setSaveStatus(""), 4000);
    }
  };

  // ------------------------------------------
  // Send slots to Discord
  // ------------------------------------------
  const sendSlots = async () => {
    if (!selectedChannel) return alert("Select a channel first!");
    try {
      setLoading(true);
      setSaveStatus("📤 Sending slots to Discord...");
      const res = await axios.post(
        `${backendURL}/api/guilds/${guildId}/send_slots`,
        { channel_id: selectedChannel },
        { headers: { "Content-Type": "application/json" } }
      );
      console.log("✅ Sent:", res.data);
      setSaveStatus("✅ Slots sent successfully!");
    } catch (err) {
      console.error("❌ Send failed:", err.response?.data || err);
      setSaveStatus("❌ Failed to send slots.");
    } finally {
      setLoading(false);
      setTimeout(() => setSaveStatus(""), 4000);
    }
  };

  // ------------------------------------------
  // Styles
  // ------------------------------------------
  const styles = {
    container: {
      maxWidth: "1200px",
      margin: "40px auto",
      fontFamily: "Arial, sans-serif",
      textAlign: "center",
    },
    table: {
      width: "100%",
      borderCollapse: "collapse",
      marginTop: "20px",
    },
    thtd: {
      border: "1px solid #ccc",
      padding: "8px",
    },
    button: {
      margin: "8px",
      padding: "10px 16px",
      border: "none",
      background: "#007bff",
      color: "white",
      borderRadius: "6px",
      cursor: "pointer",
    },
    status: {
      background: "#f3f3f3",
      padding: "10px",
      borderRadius: "6px",
      marginBottom: "10px",
      display: "inline-block",
    },
    select: { padding: "6px", borderRadius: "4px" },
    input: { padding: "4px", borderRadius: "4px" },
    emojiPreview: {
      width: "24px",
      height: "24px",
      verticalAlign: "middle",
      marginRight: "5px",
    },
  };

  // ------------------------------------------
  // UI
  // ------------------------------------------
  return (
    <div style={styles.container}>
      <h1>🎮 Slot Manager Dashboard</h1>

      {saveStatus && <div style={styles.status}>{saveStatus}</div>}

      {/* Channel Selection */}
      <div style={{ marginBottom: "20px" }}>
        <label style={{ marginRight: "10px" }}>Send to Channel:</label>
        <select
          style={styles.select}
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
        <button
          style={styles.button}
          onClick={sendSlots}
          disabled={!selectedChannel || loading}
        >
          🚀 Send Slots
        </button>
      </div>

      {/* Slots Table */}
      <table style={styles.table}>
        <thead>
          <tr>
            {[
              "Slot #",
              "Team Name",
              "Tag",
              "Emoji",
              "Background",
              "Font",
              "Size",
              "Color",
              "Pad Top",
              "Pad Bottom",
            ].map((h) => (
              <th key={h} style={styles.thtd}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {slots.map((slot, i) => (
            <tr key={i}>
              <td style={styles.thtd}>{slot.slot_number}</td>
              <td style={styles.thtd}>
                <input
                  style={styles.input}
                  value={slot.teamname}
                  onChange={(e) => updateSlot(i, "teamname", e.target.value)}
                />
              </td>
              <td style={styles.thtd}>
                <input
                  style={styles.input}
                  value={slot.teamtag}
                  onChange={(e) => updateSlot(i, "teamtag", e.target.value)}
                />
              </td>

              {/* ✅ Emoji selector with preview */}
              <td style={styles.thtd}>
                <select
                  style={styles.select}
                  value={slot.emoji}
                  onChange={(e) => updateSlot(i, "emoji", e.target.value)}
                >
                  <option value="">None</option>
                  {emojis.map((em, x) => (
                    <option key={x} value={em.name}>
                      {em.name}
                    </option>
                  ))}
                </select>
                {slot.emoji && (
                  <div style={{ marginTop: "5px" }}>
                    {(() => {
                      const em = emojis.find((e) => e.name === slot.emoji);
                      return (
                        em && (
                          <img
                            src={em.url}
                            alt={em.name}
                            title={em.name}
                            style={styles.emojiPreview}
                          />
                        )
                      );
                    })()}
                  </div>
                )}
              </td>

              {/* Background */}
              <td style={styles.thtd}>
                <select
                  style={styles.select}
                  value={slot.background_name}
                  onChange={(e) =>
                    updateSlot(i, "background_name", e.target.value)
                  }
                >
                  {gifs.map((g, y) => (
                    <option key={y} value={g.name}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </td>

              {/* Font */}
              <td style={styles.thtd}>
                <input
                  style={styles.input}
                  value={slot.font_family}
                  onChange={(e) => updateSlot(i, "font_family", e.target.value)}
                />
              </td>
              <td style={styles.thtd}>
                <input
                  type="number"
                  style={{ ...styles.input, width: "70px" }}
                  value={slot.font_size}
                  onChange={(e) =>
                    updateSlot(i, "font_size", Number(e.target.value))
                  }
                />
              </td>
              <td style={styles.thtd}>
                <input
                  type="color"
                  style={styles.input}
                  value={slot.font_color}
                  onChange={(e) => updateSlot(i, "font_color", e.target.value)}
                />
              </td>
              <td style={styles.thtd}>
                <input
                  type="number"
                  style={{ ...styles.input, width: "70px" }}
                  value={slot.padding_top}
                  onChange={(e) =>
                    updateSlot(i, "padding_top", Number(e.target.value))
                  }
                />
              </td>
              <td style={styles.thtd}>
                <input
                  type="number"
                  style={{ ...styles.input, width: "70px" }}
                  value={slot.padding_bottom}
                  onChange={(e) =>
                    updateSlot(i, "padding_bottom", Number(e.target.value))
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Action Buttons */}
      <div style={{ marginTop: "20px" }}>
        <button style={styles.button} onClick={addSlot}>
          ➕ Add Slot
        </button>
        <button style={styles.button} onClick={saveAllSlots}>
          💾 Save All Slots
        </button>
      </div>

      {loading && <div style={{ marginTop: "20px" }}>⏳ Working...</div>}
    </div>
  );
};

export default Dashboard;

