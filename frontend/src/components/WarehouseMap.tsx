"use client";
import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Loader2, Plus, Minus, Send, X, Package, Database, Brain, Sparkles, Network, CheckSquare, Search, Mic, Captions, CaptionsOff, List, ChevronLeft, RefreshCw, Square } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useVoiceMode } from '../hooks/useVoiceMode';
import { getMarkdownComponents } from './MarkdownComponents';

// Global registry to ensure unique symbols for up to 100 categories
const categorySymbolMap = new Map<string, number>();
const availableSymbols = Array.from({length: 100}, (_, i) => i);
// Shuffle symbols for randomness
for (let i = availableSymbols.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [availableSymbols[i], availableSymbols[j]] = [availableSymbols[j], availableSymbols[i]];
}

function getSymbolForCategory(category: string): number {
    const cat = (category || "").toLowerCase().trim();
    if (categorySymbolMap.has(cat)) {
        return categorySymbolMap.get(cat)!;
    }
    if (availableSymbols.length === 0) {
        return Math.floor(Math.random() * 100);
    }
    const symbol = availableSymbols.pop()!;
    categorySymbolMap.set(cat, symbol);
    return symbol;
}

export default function WarehouseMap({ animUI, allowChanges, setAllowChanges, onAgentInteraction }: { animUI: boolean, allowChanges: boolean, setAllowChanges: (v: boolean) => void, onAgentInteraction?: (q: string, r: string) => void }) {
  const submitQueryRef = useRef<(text?: string) => void>(undefined);
  const markdownComponents = useMemo(() => getMarkdownComponents((msg) => { if (submitQueryRef.current) submitQueryRef.current(msg); }), []);

  const [items, setItems] = useState<any[]>([]);
  const [racksData, setRacksData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRack, setSelectedRack] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const prevItemsRef = useRef<Set<number>>(new Set());
  const [newItems, setNewItems] = useState<Set<number>>(new Set());
  const [activeBottomPanel, setActiveBottomPanel] = useState<'search' | 'agent' | 'legend' | null>(null);
  const [legendSelectedShape, setLegendSelectedShape] = useState<number | null>(null);
  const [globalSearchQuery, setGlobalSearchQuery] = useState("");

  useEffect(() => {
      if (items.length > 0) {
          const currentIds = new Set(items.map(i => i.id));
          const newlyAdded = new Set<number>();
          if (prevItemsRef.current.size > 0) {
              currentIds.forEach(id => {
                  if (!prevItemsRef.current.has(id)) newlyAdded.add(id);
              });
          }
          prevItemsRef.current = currentIds;
          
          if (newlyAdded.size > 0) {
              setNewItems(newlyAdded);
              setTimeout(() => setNewItems(new Set()), 3000);
          }
      }
  }, [items]);

  const fetchLayout = async () => {
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/map/layout`);
      const data = await res.json();
      if (data.status === "success") {
          setItems(data.items);
          if (data.racks) setRacksData(data.racks);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { 
      fetchLayout(); 
      const interval = setInterval(fetchLayout, 5000);
      return () => clearInterval(interval);
  }, []);

  // Mini Agent state
  const [query, setQuery] = useState("");
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState("");
  const [agentResponse, setAgentResponse] = useState("");
  
  const [showCaptions, setShowCaptions] = useState(true);
  // submitQueryRef is now defined above 
  
  const abortControllerRef = useRef<AbortController | null>(null);

  const abortQuery = () => {
      if (abortControllerRef.current) {
          abortControllerRef.current.abort();
          abortControllerRef.current = null;
      }
      setAgentLoading(false);
      setAgentStatus("");
      setAgentResponse("User has stopped the response");
  };

  const { isVoiceMode, setIsVoiceMode, voiceStatus, transcript, llmReply, speakText, interrupt } = useVoiceMode((text) => {
      setQuery(text);
      if (submitQueryRef.current) submitQueryRef.current(text);
  });
  
  const submitQuery = async (overrideInput?: string) => {
    const finalQuery = overrideInput !== undefined ? overrideInput : query;
    if (!finalQuery.trim()) return;
    
    // Auto-open agent panel if not open
    if (activeBottomPanel !== 'agent') setActiveBottomPanel('agent');
    
    setAgentLoading(true);
    setAgentStatus("Routing...");
    setAgentResponse("");
    try {
      abortControllerRef.current = new AbortController();
      const formData = new FormData();
      formData.append("query", finalQuery + " (Just do it and reply concisely, I am in map view)");
      formData.append("allow_changes", allowChanges.toString());
      
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        body: formData,
        signal: abortControllerRef.current.signal
      });
      
      if (!res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6);
            if (dataStr === "[DONE]") break;
            try {
              const data = JSON.parse(dataStr);
              if (data.status) setAgentStatus(data.status);
              if (data.response !== undefined) {
                 fullContent = data.response;
              }
            } catch (e) {
              console.error("SSE JSON Parse Error in Map View:", e, dataStr);
            }
          }
        }
      }
      // Remove thinking blocks for compact agent
      const content = fullContent.replace(/<thinking>[\s\S]*?<\/thinking>/, "").trim();
      setAgentResponse(content);
      fetchLayout();
      if (onAgentInteraction) {
         onAgentInteraction(finalQuery, content);
      }
      
      if (isVoiceMode) {
          speakText(content);
      }
    } catch (e: any) {
        if (e.name === 'AbortError') {
            console.log("Query aborted by user");
        }
    } finally {
        if (abortControllerRef.current) {
            setAgentLoading(false);
            setAgentStatus("");
            setQuery("");
            abortControllerRef.current = null;
        }
    }
  };
  
  useEffect(() => {
      submitQueryRef.current = submitQuery;
  }, [submitQuery]);

  const adjustItem = async (id: number, action: string) => {
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await fetch(`${API_URL}/api/map/adjust`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: id, action })
      });
      fetchLayout();
    } catch(e) {}
  };

  const normalizeRackId = (rid: any) => {
    if (typeof rid === 'string' && rid.toLowerCase().startsWith('rack ')) return parseInt(rid.replace(/[^0-9]/g, ''));
    if (typeof rid === 'string' && rid.toLowerCase().startsWith('rack_')) return parseInt(rid.replace(/[^0-9]/g, ''));
    if (typeof rid === 'number') return rid;
    return parseInt(String(rid).replace(/[^0-9]/g, '')) || 0;
  };

  const itemsWithNormalizedRack = useMemo(() => {
      return items.map(item => ({...item, rack_id: normalizeRackId(item.rack_id)}));
  }, [items]);

  const SHAPE_NAMES = ["Square", "Circle", "Triangle Up", "Triangle Down", "Diamond", "Cross", "Pentagon", "Hexagon", "Star", "Octagon"];
  const COLORS = ["#ef476f", "#118ab2", "#06d6a0", "#ffd166", "#f77f00", "#8338ec", "#38b000", "#ff9f1c", "#9e2a2b", "#6c757d"];

  const getShapeStyle = (category: string, overrideShapeIdx?: number) => {
      const shapeIndex = overrideShapeIdx !== undefined ? overrideShapeIdx : Math.floor(getSymbolForCategory(category) / 10);
      const style: React.CSSProperties = { width: "12px", height: "12px", borderRadius: "2px", clipPath: "none", flexShrink: 0 };
      switch(shapeIndex) {
          case 1: style.borderRadius = "50%"; break;
          case 2: style.clipPath = "polygon(50% 0%, 0% 100%, 100% 100%)"; style.borderRadius = "0px"; break;
          case 3: style.clipPath = "polygon(0% 0%, 100% 0%, 50% 100%)"; style.borderRadius = "0px"; break;
          case 4: style.clipPath = "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)"; style.borderRadius = "0px"; break;
          case 5: style.clipPath = "polygon(33% 0%, 66% 0%, 66% 33%, 100% 33%, 100% 66%, 66% 66%, 66% 100%, 33% 100%, 33% 66%, 0% 66%, 0% 33%, 33% 33%)"; style.borderRadius = "0px"; break;
          case 6: style.clipPath = "polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%)"; style.borderRadius = "0px"; break;
          case 7: style.clipPath = "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)"; style.borderRadius = "0px"; break;
          case 8: style.clipPath = "polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)"; style.borderRadius = "0px"; break;
          case 9: style.clipPath = "polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%)"; style.borderRadius = "0px"; break;
      }
      return style;
  };

  const getColor = (category: string, overrideColorIdx?: number) => {
      const colorIndex = overrideColorIdx !== undefined ? overrideColorIdx : getSymbolForCategory(category) % 10;
      return COLORS[colorIndex];
  };

  const legendData = useMemo(() => {
      const cats: Record<number, Record<string, {colorIdx: number, count: number}>> = {};
      itemsWithNormalizedRack.forEach(item => {
          const cat = (item.category || "").toLowerCase();
          const symbolId = getSymbolForCategory(cat);
          const shapeIdx = Math.floor(symbolId / 10);
          const colorIdx = symbolId % 10;
          if (!cats[shapeIdx]) cats[shapeIdx] = {};
          if (!cats[shapeIdx][cat]) {
              cats[shapeIdx][cat] = { colorIdx: colorIdx, count: 0 };
          }
          cats[shapeIdx][cat].count += 1;
      });
      return cats;
  }, [itemsWithNormalizedRack]);

  const racksList = useMemo(() => {
      if (racksData && racksData.length > 0) {
          return racksData.sort((a: any, b: any) => a.id - b.id);
      }
      // Fallback if older API
      return Array.from(new Set(itemsWithNormalizedRack.map(i => i.rack_id))).sort((a: any, b: any) => a - b).map(r => ({ id: r, capacity: 600 }));
  }, [itemsWithNormalizedRack, racksData]);

  const racksItemsMap = useMemo(() => {
      const map: Record<number, any[]> = {};
      racksList.forEach(r => map[r.id as number] = []);
      itemsWithNormalizedRack.forEach(item => {
          if (map[item.rack_id]) map[item.rack_id].push(item);
      });
      return map;
  }, [itemsWithNormalizedRack, racksList]);

  const globalSearchResults = useMemo(() => {
      if (!globalSearchQuery.trim()) return {};
      const q = globalSearchQuery.toLowerCase();
      const filtered = itemsWithNormalizedRack.filter(i => 
          (i.name || '').toLowerCase().includes(q) || 
          (i.category || '').toLowerCase().includes(q) ||
          String(i.id).includes(q)
      );
      
      const map: Record<number, any[]> = {};
      filtered.forEach(item => {
          if (!map[item.rack_id]) map[item.rack_id] = [];
          map[item.rack_id].push(item);
      });
      return map;
  }, [itemsWithNormalizedRack, globalSearchQuery]);

  if (loading) return <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}><Loader2 className="animate-spin" /></div>;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden", display: "flex", flexDirection: "column", padding: "40px" }}>
      
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "40px" }}>
        <h1 style={{ color: "white", margin: 0, fontSize: "2rem", fontWeight: "600", textShadow: "0 2px 10px rgba(0,0,0,0.5)" }}>Warehouse Physical Layout</h1>
        <label className="toggle-switch" title="Allow the agent to modify the SQL inventory database">
          <input type="checkbox" checked={allowChanges} onChange={(e) => setAllowChanges(e.target.checked)} />
          <span className="slider round" style={allowChanges ? { backgroundColor: '#ef476f' } : {}}></span>
          <span className="toggle-label" style={{ color: "white", display: "flex", alignItems: "center", gap: "6px" }}><CheckSquare size={14} color={allowChanges ? '#ef476f' : '#888'} /> Allow Changes</span>
        </label>
      </div>
      
      <div style={{ display: "flex", flexWrap: "wrap", gap: "30px", flex: 1, overflowY: "auto", paddingBottom: "100px" }}>
        {racksList.map(rackObj => {
            const rack = rackObj.id;
            const rackItems = racksItemsMap[rack as number] || [];
            return (
                <div 
                  key={rack as number} 
                  className={`settings-modal ${animUI ? 'anim-pop' : ''}`}
                  style={{ 
                      width: "180px", 
                      height: "220px", 
                      position: "relative",
                      cursor: "pointer", 
                      padding: "15px", 
                      display: "flex", 
                      flexDirection: "column",
                      boxShadow: selectedRack === rack ? "0 0 20px rgba(239, 71, 111, 0.3)" : "none",
                      border: selectedRack === rack ? "2px solid rgba(255,255,255,0.6)" : "1px solid rgba(255,255,255,0.15)",
                      transition: "transform 0.3s cubic-bezier(0.25, 1, 0.5, 1), box-shadow 0.3s",
                      transformOrigin: "center",
                      willChange: "transform",
                      zIndex: selectedRack === rack ? 10 : 1
                  }}
                  onClick={() => setSelectedRack(rack as number)}
                  onMouseEnter={e => { e.currentTarget.style.transform = "scale(1.05)"; e.currentTarget.style.zIndex = "10"; }}
                  onMouseLeave={e => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.zIndex = "1"; }}
                >
                    <h3 style={{ color: "#8fa0ba", margin: "0 0 10px 0", fontSize: "0.9rem", borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "5px", flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>Rack {rack}</span>
                        <span style={{ fontSize: "0.75rem", opacity: 0.6, fontWeight: "normal" }}>{rackItems.length} / {rackObj.capacity}</span>
                    </h3>
                    <div className="rack-items-container" style={{ display: "flex", flexWrap: "wrap", gap: "6px", alignContent: "flex-start", flex: 1, overflowY: "auto", paddingRight: "4px" }}>
                        {Object.values(rackItems.reduce((acc, item) => {
                            const cat = item.category;
                            if (!acc[cat]) acc[cat] = { category: cat, count: 0, hasNew: false };
                            acc[cat].count += 1;
                            if (newItems.has(item.id)) acc[cat].hasNew = true;
                            return acc;
                        }, {} as Record<string, any>)).map((group: any) => (
                            <div key={group.category} className={`map-item-group ${animUI ? 'anim-pop' : ''} ${group.hasNew ? 'item-flash' : ''}`} style={{
                                display: "flex", alignItems: "center", gap: "6px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", padding: "4px 8px", borderRadius: "8px", flexShrink: 0
                            }} title={`${group.category} x ${group.count}`}>
                                <div style={{ 
                                    ...getShapeStyle(group.category),
                                    background: getColor(group.category)
                                }} />
                                <span style={{ fontSize: "0.8rem", color: "#8fa0ba", fontWeight: 600 }}>{group.count}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )
        })}
      </div>

      {/* Floating Side Panel for Details */}
      {selectedRack !== null && (() => {
          const allRackItems = itemsWithNormalizedRack.filter(i => i.rack_id === selectedRack);
          const filteredRackItems = allRackItems.filter(i => (i.name || '').toLowerCase().includes((searchQuery || '').toLowerCase()) || (i.category || '').toLowerCase().includes(searchQuery.toLowerCase()));
          const groupedSelected = filteredRackItems.reduce((acc, item) => {
              if (!acc[item.category]) acc[item.category] = [];
              acc[item.category].push(item);
              return acc;
          }, {} as Record<string, any[]>);

          return (
          <div className={`settings-modal ${animUI ? 'anim-slide-in' : ''}`} style={{ 
              position: "absolute", 
              right: "40px", 
              top: "40px", 
              bottom: "120px", 
              width: "350px", 
              maxWidth: "100%",
              display: "flex",
              flexDirection: "column",
              padding: "20px",
              background: "rgba(15, 23, 42, 0.8)",
              backdropFilter: "blur(16px)",
              WebkitBackdropFilter: "blur(16px)",
              zIndex: 100,
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "16px",
              boxShadow: "0 10px 40px rgba(0,0,0,0.5)"
          }}>
              <div style={{ flexShrink: 0, borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "15px", marginBottom: "15px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <h2 style={{ margin: 0 }}>Rack {selectedRack} Details</h2>
                      <button onClick={() => { setSelectedRack(null); setSearchQuery(""); }} style={{ background: "rgba(255, 255, 255, 0.15)", border: "none", color: "white", cursor: "pointer", borderRadius: "50%", width: "28px", height: "28px", display: "flex", justifyContent: "center", alignItems: "center", transition: "0.2s" }} onMouseEnter={e => e.currentTarget.style.background = "rgba(255, 255, 255, 0.25)"} onMouseLeave={e => e.currentTarget.style.background = "rgba(255, 255, 255, 0.15)"}><X size={16} /></button>
                  </div>
                  <input 
                    type="text" 
                    placeholder="Search items..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ width: "100%", marginTop: "15px", padding: "10px", borderRadius: "8px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", color: "white", outline: "none", fontSize: "0.9rem" }}
                  />
              </div>

              <div className="rack-items-container" style={{ flex: 1, overflowY: "auto", paddingRight: "5px" }}>
                  {Object.keys(groupedSelected).map(cat => (
                      <div key={cat} style={{ marginBottom: "20px" }}>
                          <h4 style={{ color: "#8fa0ba", textTransform: "uppercase", fontSize: "0.8rem", letterSpacing: "1px", marginBottom: "10px" }}>{cat} ({groupedSelected[cat].length})</h4>
                          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {groupedSelected[cat].slice(0, 50).map((item: any) => (
                                  <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(0,0,0,0.2)", padding: "8px 12px", borderRadius: "8px" }}>
                                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                          <div style={{ ...getShapeStyle(item.category), background: getColor(item.category) }} />
                                          <span style={{ fontSize: "0.9rem" }}>{item.name} <span style={{ color: "rgba(255,255,255,0.3)", fontSize: "0.7rem" }}>#{item.id}</span></span>
                                      </div>
                                      <div style={{ display: "flex", gap: "5px" }}>
                                          <button onClick={() => adjustItem(item.id, "decrement")} style={{ background: "rgba(255,89,94,0.2)", color: "#ff595e", border: "none", borderRadius: "4px", padding: "4px", cursor: "pointer" }}><Minus size={12} /></button>
                                          <button onClick={() => adjustItem(item.id, "increment")} style={{ background: "rgba(138,201,38,0.2)", color: "#8ac926", border: "none", borderRadius: "4px", padding: "4px", cursor: "pointer" }}><Plus size={12} /></button>
                                      </div>
                                  </div>
                              ))}
                              {groupedSelected[cat].length > 50 && (
                                  <div style={{ textAlign: "center", fontSize: "0.8rem", color: "#8fa0ba", padding: "4px 0", fontStyle: "italic" }}>
                                      + {groupedSelected[cat].length - 50} more items (Use AI Chat to modify in bulk)
                                  </div>
                              )}
                          </div>
                      </div>
                  ))}
                  {filteredRackItems.length === 0 && <div style={{ color: "#8fa0ba", fontStyle: "italic" }}>No items found.</div>}
              </div>
          </div>
          );
      })()}

      {/* Bottom Interactive Orbs */}
      <div style={{
          position: "absolute",
          bottom: "40px",
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          gap: "20px",
          zIndex: 100,
          alignItems: "flex-end"
      }}>
          {/* Global Search Panel */}
          <div className="input-box" style={{ 
              width: activeBottomPanel === 'search' ? "500px" : "50px", 
              height: activeBottomPanel === 'search' ? "auto" : "50px",
              borderRadius: activeBottomPanel === 'search' ? "16px" : "25px",
              padding: activeBottomPanel === 'search' ? "15px" : "0",
              maxWidth: "90vw",
              transition: "all 0.4s cubic-bezier(0.25, 1, 0.5, 1)",
              display: "flex",
              flexDirection: "column",
              justifyContent: activeBottomPanel === 'search' ? "flex-start" : "center",
              alignItems: activeBottomPanel === 'search' ? "stretch" : "center",
              cursor: activeBottomPanel === 'search' ? "default" : "pointer",
              overflow: "visible"
          }} onClick={() => { if (activeBottomPanel !== 'search') setActiveBottomPanel('search'); }}>
              {activeBottomPanel !== 'search' ? (
                  <Search size={20} color="white" />
              ) : (
                  <>
                      {/* Search Results Floating Above */}
                      {globalSearchQuery.trim() && (
                          <div className="settings-modal" style={{
                              position: "absolute",
                              bottom: "calc(100% + 15px)",
                              left: "0",
                              width: "100%",
                              background: "rgba(15, 23, 42, 0.8)",
                              backdropFilter: "blur(16px)",
                              WebkitBackdropFilter: "blur(16px)",
                              border: "1px solid rgba(255,255,255,0.1)",
                              borderRadius: "16px",
                              padding: "20px",
                              boxShadow: "0 10px 40px rgba(0,0,0,0.5)",
                              maxHeight: "calc(100vh - 200px)",
                              overflowY: "auto"
                          }}>
                              <h3 style={{ color: "white", margin: "0 0 15px 0", fontSize: "1rem" }}>Global Search Results</h3>
                              {Object.keys(globalSearchResults).length === 0 ? (
                                  <div style={{ color: "#8fa0ba", fontStyle: "italic", fontSize: "0.9rem" }}>No items match your search.</div>
                              ) : (
                                  Object.keys(globalSearchResults).map(rack => (
                                      <div key={rack} style={{ marginBottom: "15px" }}>
                                          <h4 style={{ color: "#8fa0ba", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "8px" }}>Rack {rack}</h4>
                                          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                              {globalSearchResults[rack as unknown as number].map((item: any) => (
                                                  <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(0,0,0,0.2)", padding: "8px 12px", borderRadius: "8px" }}>
                                                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                                          <div style={{ ...getShapeStyle(item.category), background: getColor(item.category) }} />
                                                          <span style={{ fontSize: "0.9rem", color: "white" }}>{item.name} <span style={{ color: "rgba(255,255,255,0.3)", fontSize: "0.7rem" }}>#{item.id}</span></span>
                                                      </div>
                                                  </div>
                                              ))}
                                          </div>
                                      </div>
                                  ))
                              )}
                          </div>
                      )}
                      
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                          <span style={{ color: "white", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}><Search size={16} /> Global Inventory Search</span>
                          <button onClick={(e) => { e.stopPropagation(); setActiveBottomPanel(null); setGlobalSearchQuery(""); }} style={{ background: "transparent", border: "none", color: "#8fa0ba", cursor: "pointer" }}><X size={18} /></button>
                      </div>
                      <input 
                          type="text" 
                          placeholder="Search any item in the warehouse..." 
                          value={globalSearchQuery}
                          onChange={e => setGlobalSearchQuery(e.target.value)}
                          style={{ width: "100%", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", padding: "10px", borderRadius: "8px", color: "white", outline: "none" }}
                          autoFocus
                      />
                  </>
              )}
          </div>

          {/* A-ware Panel */}
          <div id="map-chatbox" className="input-box" style={{ 
              width: activeBottomPanel === 'agent' ? "500px" : "50px", 
              height: activeBottomPanel === 'agent' ? "auto" : "50px",
              borderRadius: activeBottomPanel === 'agent' ? "16px" : "25px",
              padding: activeBottomPanel === 'agent' ? "15px" : "0",
              maxWidth: "90vw",
              transition: "all 0.4s cubic-bezier(0.25, 1, 0.5, 1)",
              display: "flex",
              flexDirection: "column",
              justifyContent: activeBottomPanel === 'agent' ? "flex-start" : "center",
              alignItems: activeBottomPanel === 'agent' ? "stretch" : "center",
              cursor: activeBottomPanel === 'agent' ? "default" : "pointer",
              overflow: activeBottomPanel === 'agent' ? "visible" : "hidden"
          }} onClick={() => { if (activeBottomPanel !== 'agent') setActiveBottomPanel('agent'); }}>
              {activeBottomPanel !== 'agent' ? (
                  <Sparkles size={20} color="white" />
              ) : (
                  <>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                          <span style={{ color: "white", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}><Sparkles size={16} /> A-ware</span>
                          <button onClick={(e) => { e.stopPropagation(); setActiveBottomPanel(null); }} style={{ background: "transparent", border: "none", color: "#8fa0ba", cursor: "pointer" }}><X size={18} /></button>
                      </div>
                      
                      {agentResponse && (
                          <div style={{ background: "rgba(0,0,0,0.2)", padding: "10px", borderRadius: "8px", marginBottom: "15px", fontSize: "0.9rem", color: "#e2e8f0" }}>
                              <ReactMarkdown components={markdownComponents}>{agentResponse}</ReactMarkdown>
                          </div>
                      )}
                      
                      {agentLoading && (
                          <div style={{ display: "flex", gap: "8px", alignItems: "center", color: "#8fa0ba", fontSize: "0.85rem", marginBottom: "10px" }}>
                             {agentStatus.toLowerCase().includes('sql') ? <Database className="animate-pulse" size={14} /> :
                              agentStatus.toLowerCase().includes('rout') ? <Network className="animate-pulse" size={14} /> :
                              agentStatus.toLowerCase().includes('think') ? <Brain className="animate-pulse" size={14} /> :
                              <Loader2 className="animate-spin" size={14} />} 
                             {agentStatus}
                          </div>
                      )}

                      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                          <input 
                              type="text" 
                              placeholder="Ask A-ware to move or edit items..." 
                              value={query}
                              onChange={e => setQuery(e.target.value)}
                              onKeyDown={e => { if (e.key === "Enter") submitQuery(); }}
                              style={{ flex: 1, background: "transparent", border: "none", color: "white", outline: "none" }}
                              disabled={agentLoading}
                              autoFocus
                          />
                          {agentLoading ? (
                              <button onClick={abortQuery} style={{ background: "rgba(255,89,94,0.2)", border: "none", padding: "8px", borderRadius: "8px", color: "#ff595e", cursor: "pointer" }} title="Stop Generating">
                                  <Square size={16} fill="currentColor" />
                              </button>
                          ) : (
                              <button onClick={() => submitQuery()} disabled={!query.trim()} style={{ background: "rgba(255,255,255,0.1)", border: "none", padding: "8px", borderRadius: "8px", color: "white", cursor: !query.trim() ? "not-allowed" : "pointer" }} title="Send">
                                  <Send size={16} />
                              </button>
                          )}
                          <button onClick={() => setIsVoiceMode(true)} style={{ background: "rgba(255,255,255,0.1)", border: "none", padding: "8px", borderRadius: "8px", color: "white", cursor: "pointer", marginLeft: "2px" }} title="Start Voice Mode">
                              <Mic size={16} />
                          </button>
                      </div>
                  </>
              )}
          </div>

          {/* Legend Panel */}
          <div id="map-legend" className="input-box" style={{ 
              width: activeBottomPanel === 'legend' ? "350px" : "50px", 
              height: activeBottomPanel === 'legend' ? "auto" : "50px",
              borderRadius: activeBottomPanel === 'legend' ? "16px" : "25px",
              padding: activeBottomPanel === 'legend' ? "20px" : "0",
              maxWidth: "90vw",
              transition: "all 0.4s cubic-bezier(0.25, 1, 0.5, 1)",
              display: "flex",
              flexDirection: "column",
              justifyContent: activeBottomPanel === 'legend' ? "flex-start" : "center",
              alignItems: activeBottomPanel === 'legend' ? "stretch" : "center",
              cursor: activeBottomPanel === 'legend' ? "default" : "pointer",
              overflow: "hidden"
          }} onClick={() => { if (activeBottomPanel !== 'legend') { setActiveBottomPanel('legend'); setLegendSelectedShape(null); } }}>
              {activeBottomPanel !== 'legend' ? (
                  <List size={20} color="white" />
              ) : (
                  <>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                          <span style={{ color: "white", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px", fontWeight: "600" }}>
                              {legendSelectedShape !== null && (
                                  <button onClick={(e) => { e.stopPropagation(); setLegendSelectedShape(null); }} style={{ background: "transparent", border: "none", color: "#8fa0ba", cursor: "pointer", display: "flex", alignItems: "center" }}>
                                      <ChevronLeft size={16} />
                                  </button>
                              )}
                              <List size={16} /> 
                              {legendSelectedShape === null ? "Legend Overview" : `${SHAPE_NAMES[legendSelectedShape]} Items`}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <button onClick={(e) => { e.stopPropagation(); fetchLayout(); }} style={{ background: "transparent", border: "none", color: "#8fa0ba", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px", fontSize: "0.8rem" }} title="Force Refresh">
                                  <RefreshCw size={14} /> Refresh
                              </button>
                              <button onClick={(e) => { e.stopPropagation(); setActiveBottomPanel(null); }} style={{ background: "transparent", border: "none", color: "#8fa0ba", cursor: "pointer" }}><X size={18} /></button>
                          </div>
                      </div>

                      <div style={{ maxHeight: "300px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
                          {legendSelectedShape === null ? (
                              // Level 1: List existing shapes
                              Object.keys(legendData).length === 0 ? (
                                  <div style={{ color: "#8fa0ba", fontSize: "0.9rem", fontStyle: "italic" }}>No items in warehouse.</div>
                              ) : (
                                  Object.keys(legendData).map((shapeStr) => {
                                      const shapeIdx = parseInt(shapeStr);
                                      const shapeCount = Object.values(legendData[shapeIdx]).reduce((acc, cur) => acc + cur.count, 0);
                                      return (
                                          <div key={shapeIdx} onClick={(e) => { e.stopPropagation(); setLegendSelectedShape(shapeIdx); }} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", background: "rgba(255,255,255,0.05)", borderRadius: "8px", cursor: "pointer" }}>
                                              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                                  <div style={{ ...getShapeStyle("", shapeIdx), background: "#8fa0ba" }} />
                                                  <span style={{ color: "white", fontSize: "0.9rem" }}>{SHAPE_NAMES[shapeIdx]}</span>
                                              </div>
                                              <span style={{ color: "#8fa0ba", fontSize: "0.8rem", background: "rgba(0,0,0,0.3)", padding: "2px 8px", borderRadius: "10px" }}>{shapeCount} items</span>
                                          </div>
                                      );
                                  })
                              )
                          ) : (
                              // Level 2: List categories for this shape
                              Object.entries(legendData[legendSelectedShape] || {}).map(([catName, data]) => {
                                  return (
                                      <div key={catName} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", background: "rgba(255,255,255,0.05)", borderRadius: "8px" }}>
                                          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                              <div style={{ ...getShapeStyle("", legendSelectedShape), background: COLORS[data.colorIdx] }} />
                                              <span style={{ color: "white", fontSize: "0.9rem", textTransform: "capitalize" }}>{catName}</span>
                                          </div>
                                          <span style={{ color: "#8fa0ba", fontSize: "0.8rem", background: "rgba(0,0,0,0.3)", padding: "2px 8px", borderRadius: "10px" }}>{data.count} items</span>
                                      </div>
                                  );
                              })
                          )}
                      </div>
                  </>
              )}
          </div>
      </div>
      
      {isVoiceMode && (
        <div className="voice-overlay">
          <div className="voice-controls">
            <button className="voice-btn" onClick={() => setShowCaptions(!showCaptions)} title="Toggle Captions">
              {showCaptions ? <Captions size={24} /> : <CaptionsOff size={24} />}
            </button>
            <button className="voice-btn danger" onClick={() => setIsVoiceMode(false)} title="Close Voice Mode">
              <X size={32} />
            </button>
          </div>
          {showCaptions && (
            <div className="voice-captions">
              {voiceStatus === 'listening' ? transcript || "Listening..." : null}
              {voiceStatus === 'thinking' ? "Thinking..." : null}
              {voiceStatus === 'speaking' ? llmReply : null}
              {voiceStatus === 'idle' ? "..." : null}
            </div>
          )}
          <div className={`voice-orb ${voiceStatus}`} onClick={() => {
              if (voiceStatus === 'thinking' || voiceStatus === 'speaking') {
                  if (agentLoading) abortQuery();
                  interrupt();
              }
          }} />
        </div>
      )}
    </div>
  );
}
