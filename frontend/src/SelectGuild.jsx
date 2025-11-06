import React, { useEffect, useState } from "react";
import axios from "axios";

const backendURL = "https://slotmanager-backend.onrender.com";
const frontendURL = window.location.origin;

const SelectGuild = () => {
  const [guilds, setGuilds] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // Parse URL params after redirect from /auth/callback
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const guildData = params.get("guilds");
    const username = params.get("username");
    const userId = params.get("user_id");

    if (token) {
      // ✅ Save token in localStorage for later API calls
      localStorage.setItem("discord_token", token);
    }

    if (guildData) {
      try {
        const parsedGuilds = JSON.parse(decodeURIComponent(guildData));
        setGuilds(parsedGuilds);
      } catch (err) {
        console.error("Failed to parse guild data:", err);
        setError("Could not load your servers.");
      }
    }

    if (username && userId) {
      setUser({ id: userId, username });
    }

    setLoading(false);
  }, []);

  const handleGuildSelect = (guildId) => {
    const token = localStorage.getItem("discord_token");
    if (!token) {
      alert("No token found. Please log in again.");
      window.location.href = `${backendURL}/login`;
      return;
    }

    // Redirect to Dashboard with guild_id in URL
    window.location.href = `${frontendURL}/dashboard?guild_id=${guildId}`;
  };

  const handleLogin = () => {
    // Start Discord OAuth login flow
    window.location.href = `${backendURL}/login`;
  };

  if (loading) {
    return <div style={{ textAlign: "center", marginTop: "40px" }}>Loading...</div>;
  }

  if (error) {
    return <div style={{ textAlign: "center", color: "red" }}>{error}</div>;
  }

  return (
    <div
      style={{
        maxWidth: "600px",
        margin: "50px auto",
        textAlign: "center",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <h1>🪄 Select a Discord Server</h1>

      {user ? (
        <p>
          Logged in as <strong>{user.username}</strong>
        </p>
      ) : (
        <p>Log in to manage your servers.</p>
      )}

      {!user && (
        <button
          style={{
            padding: "10px 20px",
            background: "#5865F2",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
          }}
          onClick={handleLogin}
        >
          Login with Discord
        </button>
      )}

      {user && guilds.length > 0 && (
        <div style={{ marginTop: "20px" }}>
          <h3>Your Servers</h3>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {guilds.map((guild) => (
              <li
                key={guild.id}
                onClick={() => handleGuildSelect(guild.id)}
                style={{
                  margin: "10px 0",
                  padding: "10px",
                  border: "1px solid #ccc",
                  borderRadius: "6px",
                  cursor: "pointer",
                  transition: "0.2s",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.backgroundColor = "#f3f3f3")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.backgroundColor = "white")
                }
              >
                <strong>{guild.name}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}

      {user && guilds.length === 0 && (
        <p>You don’t have any servers with Manage Server permission.</p>
      )}
    </div>
  );
};

export default SelectGuild;
