import React, { useState, useEffect } from "react";
import axios from "axios";

export default function SlotEditor({backend, guildId, slot, refresh}){
  const [teamname,setTeamname] = useState(slot.teamname || "");
  const [teamtag,setTeamtag] = useState(slot.teamtag || "");
  const [emoji,setEmoji] = useState(slot.emoji || "");
  const [fontColor,setFontColor] = useState(slot.font_color || "#FFFFFF");
  const [fontSize,setFontSize] = useState(slot.font_size || 48);
  const [paddingTop,setPaddingTop] = useState(slot.padding_top || 0);       // NEW
  const [paddingBottom,setPaddingBottom] = useState(slot.padding_bottom || 0);// NEW
  const [previewUrl,setPreviewUrl] = useState(slot.background_url || `${backend}/api/generate/${guildId}/${slot.slot_number}`);

  useEffect(()=> {
    setTeamname(slot.teamname||"");
    setTeamtag(slot.teamtag||"");
    setEmoji(slot.emoji||"");
    setFontColor(slot.font_color||"#FFFFFF");
    setFontSize(slot.font_size||48);
    setPaddingTop(slot.padding_top||0);
    setPaddingBottom(slot.padding_bottom||0);
    setPreviewUrl(slot.background_url || `${backend}/api/generate/${guildId}/${slot.slot_number}`);
  }, [slot]);

  async function save(){
    await axios.post(`${backend}/api/guilds/${guildId}/slots/${slot.slot_number}`, {
      slot_number: slot.slot_number,
      teamname,
      teamtag,
      emoji,
      font_family: "DejaVuSans.ttf",
      font_size: fontSize,
      font_color: fontColor,
      is_gif: slot.is_gif ? 1 : 0,
      padding_top: parseInt(paddingTop)||0,
      padding_bottom: parseInt(paddingBottom)||0
    });
    refresh();
    alert("Saved");
  }

  async function uploadBackground(file){
    const fd = new FormData();
    fd.append("file", file);
    const r = await axios.post(`${backend}/api/guilds/${guildId}/slots/${slot.slot_number}/upload`, fd, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    setPreviewUrl(r.data.url || `${backend}/api/generate/${guildId}/${slot.slot_number}`);
    refresh();
  }

  async function preview(){
    setPreviewUrl(`${backend}/api/generate/${guildId}/${slot.slot_number}?_t=${Date.now()}`);
  }

  async function sendSlot(){
    alert(`To send slot to channel: in Discord use slash command /send_slot and provide guild_id=${guildId} and slot=${slot.slot_number}`);
  }

  return (
    <div className="border p-3 rounded">
      <div className="flex gap-4">
        <div className="w-64">
          <img className="preview" src={previewUrl} alt="preview" />
        </div>
        <div className="flex-1">
          <div className="mb-2 font-semibold">Slot #{slot.slot_number}</div>
          <div className="flex gap-2 mb-2">
            <input value={teamname} onChange={e=>setTeamname(e.target.value)} placeholder="Team name" className="p-2 border rounded flex-1" />
            <input value={teamtag} onChange={e=>setTeamtag(e.target.value)} placeholder="Team tag" className="p-2 border rounded w-40" />
            <input value={emoji} onChange={e=>setEmoji(e.target.value)} placeholder="Emoji" className="p-2 border rounded w-24" />
          </div>

          <div className="flex gap-2 items-center mb-2">
            <label className="text-sm">Font color</label>
            <input type="color" value={fontColor} onChange={e=>setFontColor(e.target.value)} />
            <label className="text-sm">Size</label>
            <input type="number" value={fontSize} onChange={e=>setFontSize(parseInt(e.target.value)||48)} className="w-20 p-1 border rounded" />
          </div>

          <div className="flex gap-2 items-center mb-2">
            <label className="text-sm">Padding top (px)</label>
            <input type="number" value={paddingTop} onChange={e=>setPaddingTop(e.target.value)} className="w-20 p-1 border rounded" />
            <label className="text-sm">Padding bottom (px)</label>
            <input type="number" value={paddingBottom} onChange={e=>setPaddingBottom(e.target.value)} className="w-20 p-1 border rounded" />
          </div>

          <div className="flex gap-2 items-center">
            <input type="file" onChange={e => uploadBackground(e.target.files[0])} />
            <button onClick={save} className="px-3 py-1 bg-blue-600 text-white rounded">Save</button>
            <button onClick={preview} className="px-3 py-1 bg-gray-600 text-white rounded">Preview</button>
            <button onClick={sendSlot} className="px-3 py-1 bg-green-600 text-white rounded">How to Send</button>
          </div>
        </div>
      </div>
    </div>
  );
}
