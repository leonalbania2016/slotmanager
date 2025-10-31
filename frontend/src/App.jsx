import React, { useEffect, useState } from "react";
import axios from "axios";
import SlotEditor from "./components/SlotEditor";

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function App(){
  const [guilds, setGuilds] = useState([]);
  const [accessToken, setAccessToken] = useState("");
  const [selectedGuild, setSelectedGuild] = useState(null);
  const [slots, setSlots] = useState([]);
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState("");

  useEffect(()=>{
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");
    if(code && !accessToken){
      axios.get(`${BACKEND}/auth/callback?code=${code}`)
        .then(r => {
          setGuilds(r.data.guilds || []);
          setAccessToken(r.data.access_token || "");
        })
        .catch(err => console.error(err));
    }
  }, []);

  async function loadSlots(guildId){
    const r = await axios.get(`${BACKEND}/api/guilds/${guildId}/slots`);
    setSlots(r.data);
  }

  async function loadChannels(guildId){
    const r = await axios.get(`${BACKEND}/api/guilds/${guildId}/channels`);
    setChannels(r.data.channels || []);
  }

  function onGuildSelect(e){
    const id = e.target.value;
    setSelectedGuild(id);
    if(id){
      loadSlots(id);
      loadChannels(id);
      axios.get(`${BACKEND}/api/guilds/${id}/channel`).then(r => setSelectedChannel(r.data.channel_id || ""));
    } else {
      setSlots([]);
      setChannels([]);
    }
  }

  async function setChannel(){
    if(!selectedGuild) return alert("Choose guild");
    await axios.post(`${BACKEND}/api/guilds/${selectedGuild}/channel`, new URLSearchParams({channel_id: selectedChannel}));
    alert("Channel saved");
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Slot Dashboard</h1>
      <div className="mb-4">
        {guilds.length === 0 ? (
          <a href={`${BACKEND}/auth/login`} className="px-4 py-2 bg-blue-600 text-white rounded">Login with Discord</a>
        ) : (
          <div className="flex gap-4 items-center">
            <select onChange={onGuildSelect} className="p-2 border rounded">
              <option value="">Select guild</option>
              {guilds.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            {selectedGuild && (
              <>
                <select value={selectedChannel} onChange={(e)=>setSelectedChannel(e.target.value)} className="p-2 border rounded">
                  <option value="">-- choose channel --</option>
                  {channels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <button onClick={setChannel} className="px-3 py-2 bg-green-600 text-white rounded">Save Channel</button>
              </>
            )}
          </div>
        )}
      </div>

      {selectedGuild && (
        <div>
          <h2 className="text-xl font-semibold mb-2">Slots (2-25)</h2>
          <div className="grid grid-cols-1 gap-4">
            {slots.map(s => (
              <SlotEditor key={s.slot_number} backend={BACKEND} guildId={selectedGuild} slot={s} refresh={() => loadSlots(selectedGuild)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
