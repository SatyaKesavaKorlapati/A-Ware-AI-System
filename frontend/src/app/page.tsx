"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Send, ImagePlus, ChevronDown, ChevronRight, Loader2, X, Plus, MessageSquare, Menu, PanelLeftClose, User, Zap, Pin, PinOff, CheckSquare, Square, MoreVertical, Edit2, Copy, Trash2, Sidebar, Database, Network, Sparkles, Brain, Map, Mic, MicOff, Captions, CaptionsOff } from "lucide-react";
import WarehouseMap from "../components/WarehouseMap";
import { useVoiceMode } from "../hooks/useVoiceMode";

type Message = {
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  images?: string[];
  isTyping?: boolean;
};

type ImageContext = {
  id: string;
  base64: string;
  isPinned: boolean;
  isSelected: boolean;
};

type ChatSession = {
  emoji?: string;
  id: string;
  title: string;
  messages: Message[];
  imageQueue: ImageContext[];
  is_pinned?: boolean;
  updated_at?: number;
};

// Typing Effect Component
const Typewriter = ({ text, onComplete, onAction }: { text: string, onComplete?: () => void, onAction?: (label: string) => void }) => {
  const [displayed, setDisplayed] = useState("");
  
  useEffect(() => {
    let index = 0;
    const interval = setInterval(() => {
      setDisplayed(text.slice(0, index));
      index += 2;
      if (index > text.length) {
        clearInterval(interval);
        setDisplayed(text);
        if (onComplete) onComplete();
      }
    }, 15);
    return () => clearInterval(interval);
  }, [text]);

  return <ReactMarkdown components={{
    a: ({ node, ...props }) => {
      if (props.href?.startsWith("#action-")) {
        const actionName = props.children?.toString().toLowerCase() || "";
        let bg = "rgba(0, 112, 243, 0.2)";
        let border = "1px solid rgba(0, 112, 243, 0.5)";
        if (actionName.includes("yes")) {
          bg = "rgba(16, 185, 129, 0.2)";
          border = "1px solid rgba(16, 185, 129, 0.5)";
        } else if (actionName.includes("no")) {
          bg = "rgba(239, 68, 68, 0.2)";
          border = "1px solid rgba(239, 68, 68, 0.5)";
        }
        return (
          <button 
            style={{ backgroundColor: bg, border: border, backdropFilter: 'blur(8px)', color: 'white', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', margin: '8px 8px 4px 0', fontWeight: 600, fontSize: '0.9rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
            onClick={(e) => { e.preventDefault(); if (onAction) onAction(props.children as string); }}
          >
            {props.children}
          </button>
        );
      }
      return <a {...props} />;
    },
    code: ({ node, inline, className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || '');
      if (!inline && match && match[1] === 'timeline') {
        return <TimelineWidget jsonStr={String(children).replace(/\n$/, '')} onAction={(msg) => { if (onAction) onAction(msg); }} />;
      }
      return <code className={className} {...props}>{children}</code>;
    }
  }}>{displayed}</ReactMarkdown>;
};

const TimelineWidget = ({ jsonStr, onAction }: { jsonStr: string, onAction: (msg: string) => void }) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submittedState, setSubmittedState] = useState<string | null>(null);
  
  let items = [];
  try { items = JSON.parse(jsonStr); } catch (e) {}

  if (submittedState === 'cancelled') {
    return <div className="timeline-marker cancelled">❌ Action Cancelled</div>;
  }
  if (submittedState) {
    const selectedItem = items.find((i: any) => i.id === submittedState);
    return <div className="timeline-marker restored">⏪ Restored to: {selectedItem?.desc || submittedState}</div>;
  }

  return (
    <div className="timeline-glass-box">
      <div className="timeline-header">
        <Database size={16} style={{marginRight: '8px', color: '#60a5fa'}} />
        Interactive Database Timeline
      </div>
      <div className="timeline-list">
        {items.map((item: any) => (
          <div 
            key={item.id} 
            className={`timeline-item ${selectedId === item.id ? 'selected' : ''}`}
            onClick={() => setSelectedId(item.id)}
          >
            <div className="timeline-date">{item.date}</div>
            <div className="timeline-desc">{item.desc}</div>
          </div>
        ))}
      </div>
      <div className="timeline-footer">
        <button 
          className="timeline-btn cancel" 
          onClick={() => setSubmittedState('cancelled')}
        >
          Cancel
        </button>
        <button 
          className={`timeline-btn restore ${selectedId ? 'active' : ''}`}
          disabled={!selectedId}
          onClick={() => {
            if (selectedId) {
              setSubmittedState(selectedId);
              onAction("restore_" + selectedId);
            }
          }}
        >
          Restore State
        </button>
      </div>
    </div>
  );
};

const EMOJIS = ['💬', '🤖', '🧠', '📦', '🏭', '⚡', '🔥', '🚀', '💡', '🛠️', '⚙️', '📊', '🎯', '🌟', '📱', '💻', '🌐', '🔍', '📈', '🛡️'];

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [imageQueue, setImageQueue] = useState<ImageContext[]>([]);
  
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isHoveringLogo, setIsHoveringLogo] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [isResizing, setIsResizing] = useState(false);
  
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const newWidth = Math.max(200, Math.min(e.clientX, 600));
      setSidebarWidth(newWidth);
    };
    const handleMouseUp = () => {
      setIsResizing(false);
    };
    
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    }
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  const [yoloBypass, setYoloBypass] = useState(false);
  const [allowChanges, setAllowChanges] = useState(false);
  const [popoutOpen, setPopoutOpen] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [animText, setAnimText] = useState(true);
  const [animUI, setAnimUI] = useState(true);
  const [animRainbow, setAnimRainbow] = useState(true);
  
  const [showCaptions, setShowCaptions] = useState(true);

  // Define sendMessage before useVoiceMode
  const sendMessageRef = useRef<(text?: string) => void>(undefined);

  const abortControllerRef = useRef<AbortController | null>(null);

  const abortQuery = () => {
      if (abortControllerRef.current) {
          abortControllerRef.current.abort();
          abortControllerRef.current = null;
      }
      setIsLoading(false);
      setLoadingStatus("");
      setMessages(prev => {
          const newMsgs = [...prev];
          if (newMsgs.length > 0 && newMsgs[newMsgs.length - 1].role === 'assistant') {
              newMsgs[newMsgs.length - 1] = {
                  ...newMsgs[newMsgs.length - 1],
                  content: "User has stopped the response",
                  isTyping: false
              };
          } else {
              newMsgs.push({ role: 'assistant', content: "User has stopped the response", isTyping: false });
          }
          return newMsgs;
      });
  };

  const { isVoiceMode, setIsVoiceMode, voiceStatus, transcript, llmReply, speakText, interrupt } = useVoiceMode((text) => {
      if (sendMessageRef.current) sendMessageRef.current(text);
  });
  const [animChatOpen, setAnimChatOpen] = useState(true);
  const [animDeleteChat, setAnimDeleteChat] = useState(true);
  const [animSpeed, setAnimSpeed] = useState(0.3);
  const [vaporizingSessionId, setVaporizingSessionId] = useState<string | null>(null);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);
  const [appMode, setAppMode] = useState<"chat" | "map">("chat");

  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renamingText, setRenamingText] = useState("");

  const [emojiPickerId, setEmojiPickerId] = useState<string | null>(null);
  const [emojiPickerPos, setEmojiPickerPos] = useState({ top: 0, left: 0 });
  const [customEmoji, setCustomEmoji] = useState("");

  useEffect(() => {
    document.documentElement.style.setProperty('--anim-speed', `${animSpeed}s`);
  }, [animSpeed]);


  useEffect(() => {
    const closeMenu = () => { setActiveMenuId(null); setEmojiPickerId(null); setProfileMenuOpen(false); };
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  // Load Sessions
  useEffect(() => {
    fetch("http://localhost:8000/api/sessions")
      .then(res => res.json())
      .then((data: ChatSession[]) => {
        setSessions(data);
        startNewSession();
      })
      .catch(err => {
        console.error("Failed to load sessions", err);
        startNewSession();
      });
  }, []);

  const saveCurrentSessionToDB = async (id: string, defaultTitle: string, msgs: Message[], queue: ImageContext[]) => {
    setSessions(prev => {
      const exists = prev.find(p => p.id === id);
      const title = exists ? exists.title : defaultTitle;
      const emoji = exists ? exists.emoji : undefined;
      const is_pinned = exists ? exists.is_pinned : false;
      const s: ChatSession = { id, title, emoji, messages: msgs, imageQueue: queue, is_pinned, updated_at: Date.now() };
      
      fetch("http://localhost:8000/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(s)
      }).catch(console.error);

      if (exists) return prev.map(p => p.id === id ? s : p);
      return [...prev, s];
    });
  };

  const startNewSession = () => {
    const id = "session_" + Date.now();
    setCurrentSessionId(id);
    setMessages([]);
    setImageQueue([]);
    setInput("");
    setSelectedFiles([]);
    setPreviews([]);
    if (animChatOpen) setChatKey(prev => prev + 1);
  };

  const loadSession = (s: ChatSession) => {
    setCurrentSessionId(s.id);
    setMessages((s.messages || []).map(m => ({ ...m, isTyping: false })));
    setImageQueue(s.imageQueue || []);
    setInput("");
    setSelectedFiles([]);
    setPreviews([]);
    if (animChatOpen) setChatKey(prev => prev + 1);
  };

  const toggleSessionPin = async (id: string, currentPinStatus: boolean) => {
    const newStatus = !currentPinStatus;
    setSessions(prev => prev.map(s => s.id === id ? { ...s, is_pinned: newStatus } : s));
    try {
      await fetch(`http://localhost:8000/api/sessions/${id}/pin`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_pinned: newStatus })
      });
    } catch (e) {}
    setActiveMenuId(null);
  };

  
  const startRename = (id: string, currentTitle: string) => {
    setRenamingSessionId(id);
    setRenamingText(currentTitle);
    setActiveMenuId(null);
  };

  const finishRename = async (id: string) => {
    if (!renamingText.trim()) {
      setRenamingSessionId(null);
      return;
    }
    try {
      await fetch(`http://localhost:8000/api/sessions/${id}/title`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: renamingText })
      });
      setSessions(prev => prev.map(s => s.id === id ? { ...s, title: renamingText } : s));
    } catch(e) {}
    setRenamingSessionId(null);
  };

  const changeEmoji = (id: string, newEmoji: string) => {
    if (!newEmoji.trim()) return;
    const sessionToSave = sessions.find(s => s.id === id);
    setSessions(prev => prev.map(s => s.id === id ? { ...s, emoji: newEmoji } : s));
    setEmojiPickerId(null);
    setCustomEmoji("");
    
    if (sessionToSave) {
       fetch("http://localhost:8000/api/sessions", {
         method: "POST",
         headers: { "Content-Type": "application/json" },
         body: JSON.stringify({ ...sessionToSave, emoji: newEmoji })
       }).catch(console.error);
    }
  };


  const deleteSession = (id: string) => {
    setSessionToDelete(id);
    setActiveMenuId(null);
  };

  const confirmDelete = async (id: string) => {
    setSessionToDelete(null);
    if (animDeleteChat) {
      setVaporizingSessionId(id);
      setTimeout(async () => {
        try {
          await fetch(`http://localhost:8000/api/sessions/${id}`, { method: "DELETE" });
          setSessions(prev => prev.filter(s => s.id !== id));
          if (currentSessionId === id) startNewSession();
        } catch(e) {}
        setVaporizingSessionId(null);
      }, animSpeed * 1000);
    } else {
      try {
        await fetch(`http://localhost:8000/api/sessions/${id}`, { method: "DELETE" });
        setSessions(prev => prev.filter(s => s.id !== id));
        if (currentSessionId === id) startNewSession();
      } catch(e) {}
    }
  };

  const generateTitle = async (query: string, sid: string) => {
    try {
      const res = await fetch("http://localhost:8000/api/generate-title", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      const title = data.title;
      
      setSessions(prev => prev.map(s => s.id === sid ? { ...s, title } : s));
      await fetch(`http://localhost:8000/api/sessions/${sid}/title`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
      });
    } catch(e) {}
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      const container = messagesEndRef.current.parentElement;
      if (container) {
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
      }
    }
  }, [messages, loadingStatus]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...files]);
      files.forEach((file) => {
        const reader = new FileReader();
        reader.onloadend = () => setPreviews((p) => [...p, reader.result as string]);
        reader.readAsDataURL(file);
      });
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      setSelectedFiles((prev) => [...prev, ...files]);
      files.forEach((file) => {
        const reader = new FileReader();
        reader.onloadend = () => setPreviews((p) => [...p, reader.result as string]);
        reader.readAsDataURL(file);
      });
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((f) => f.filter((_, i) => i !== index));
    setPreviews((p) => p.filter((_, i) => i !== index));
  };

  const parseThinking = (text: string) => {
    const thinkingMatch = text.match(/<thinking>([\s\S]*?)<\/thinking>/);
    if (thinkingMatch) {
      const thinking = thinkingMatch[1].trim();
      const content = text.replace(/<thinking>[\s\S]*?<\/thinking>/, "").trim();
      return { thinking, content };
    }
    const openMatch = text.match(/<thinking>([\s\S]*)/);
    if (openMatch) {
      return { thinking: openMatch[1].trim(), content: "" };
    }
    return { thinking: undefined, content: text.trim() };
  };

  const togglePin = (id: string) => {
    const updated = imageQueue.map(q => q.id === id ? { ...q, isPinned: !q.isPinned } : q);
    setImageQueue(updated);
    saveCurrentSessionToDB(currentSessionId, sessions.find(s=>s.id===currentSessionId)?.title || "New Session", messages, updated);
  };

  const toggleSelect = (id: string) => {
    const updated = imageQueue.map(q => q.id === id ? { ...q, isSelected: !q.isSelected } : q);
    setImageQueue(updated);
    saveCurrentSessionToDB(currentSessionId, sessions.find(s=>s.id===currentSessionId)?.title || "New Session", messages, updated);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const editMessage = (index: number) => {
    const msg = messages[index];
    if (msg.role !== "user") return;
    setInput(msg.content);
    // Remove this message and all after it
    const newMsgs = messages.slice(0, index);
    setMessages(newMsgs);
    saveCurrentSessionToDB(currentSessionId, sessions.find(s=>s.id===currentSessionId)?.title || "New Session", newMsgs, imageQueue);
  };

  const sendMessage = async (overrideInput?: string) => {
    const currentInput = overrideInput !== undefined ? overrideInput : input;
    if (!currentInput.trim() && selectedFiles.length === 0) return;

    const isFirstMessage = messages.length === 0;
    const userMessage: Message = {
      role: "user",
      content: currentInput,
      images: previews.length > 0 ? [...previews] : undefined,
    };
    
    const updatedMsgs = [...messages, userMessage];
    setMessages(updatedMsgs);
    setInput("");
    
    const newContexts: ImageContext[] = previews.map((p, idx) => ({
      id: `img_${Date.now()}_${idx}`,
      base64: p,
      isPinned: false,
      isSelected: true,
    }));
    
    const nextQueue = [...imageQueue, ...newContexts];
    while (nextQueue.length > 5) {
      const oldestUnpinnedIndex = nextQueue.findIndex(q => !q.isPinned);
      if (oldestUnpinnedIndex !== -1) nextQueue.splice(oldestUnpinnedIndex, 1);
      else nextQueue.shift();
    }
    setImageQueue(nextQueue);
    
    let sessionTitle = sessions.find(s => s.id === currentSessionId)?.title || "New Session";
    if (isFirstMessage) sessionTitle = "Generating Title...";
    
    await saveCurrentSessionToDB(currentSessionId, sessionTitle, updatedMsgs, nextQueue);
    
    if (isFirstMessage) {
      generateTitle(currentInput, currentSessionId);
    }
    
    setPreviews([]);
    const currentFiles = [...selectedFiles];
    setSelectedFiles([]);
    
    setIsLoading(true);
    setLoadingStatus("Connecting to A-Ware server...");

    try {
      abortControllerRef.current = new AbortController();
      const formData = new FormData();
      formData.append("query", currentInput);
      formData.append("use_yolo_only", yoloBypass.toString());
      formData.append("allow_changes", allowChanges.toString());
      
      const historyStr = JSON.stringify(updatedMsgs.map(m => ({ role: m.role, content: m.content })));
      const historyBlob = new Blob([historyStr], { type: 'application/json' });
      formData.append("history_file", historyBlob, "history.json");

      const activeContextImages = nextQueue.filter(q => q.isSelected).map(q => q.base64);
      const contextBlob = new Blob([JSON.stringify(activeContextImages)], { type: 'application/json' });
      formData.append("context_images_file", contextBlob, "context_images.json");
      
      currentFiles.forEach((file) => formData.append("files", file));

      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        body: formData,
        signal: abortControllerRef.current.signal
      });

      if (!res.ok) throw new Error("Server Error");

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No readable stream");

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || "";
        
        for (const line of parts) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '');
            try {
              const data = JSON.parse(dataStr);
              if (data.status) setLoadingStatus(data.status);
              
              if (data.response !== undefined) {
                const { thinking, content } = parseThinking(data.response);
                const assistantMessage: Message = {
                  role: "assistant",
                  content,
                  thinking,
                  images: data.annotated_images && data.annotated_images.length > 0 ? data.annotated_images : undefined,
                  isTyping: true
                };
                const finalMsgs = [...updatedMsgs, assistantMessage];
                setMessages(finalMsgs);
                const st = sessions.find(s => s.id === currentSessionId)?.title || "New Session";
                await saveCurrentSessionToDB(currentSessionId, st, finalMsgs, nextQueue);
                
                // Voice mode speech trigger
                if (isVoiceMode) {
                   speakText(content);
                }
              }
            } catch (e) {
              console.error("SSE JSON Parse Error:", e, dataStr);
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
          console.log("Query aborted by user");
      } else {
          console.error(err);
          const errMsgs = [...updatedMsgs, { role: "assistant" as const, content: "Sorry, I encountered an error connecting to the backend API." }];
          setMessages(errMsgs);
          saveCurrentSessionToDB(currentSessionId, sessionTitle, errMsgs, nextQueue);
      }
    } finally {
      if (abortControllerRef.current) {
          setIsLoading(false);
          setLoadingStatus("");
          abortControllerRef.current = null;
      }
    }
  };
  
  const markdownComponents = useMemo(() => ({
    a: ({ node, ...props }: any) => {
      if (props.href?.startsWith("#action-")) {
        const actionName = props.children?.toString().toLowerCase() || "";
        let bg = "rgba(0, 112, 243, 0.2)";
        let border = "1px solid rgba(0, 112, 243, 0.5)";
        if (actionName.includes("yes")) {
          bg = "rgba(16, 185, 129, 0.2)";
          border = "1px solid rgba(16, 185, 129, 0.5)";
        } else if (actionName.includes("no")) {
          bg = "rgba(239, 68, 68, 0.2)";
          border = "1px solid rgba(239, 68, 68, 0.5)";
        }
        return (
          <button 
            style={{ backgroundColor: bg, border: border, backdropFilter: 'blur(8px)', color: 'white', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', margin: '8px 8px 4px 0', fontWeight: 600, fontSize: '0.9rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
            onClick={(e) => { e.preventDefault(); if (sendMessageRef.current) sendMessageRef.current(props.children as string); }}
          >
            {props.children}
          </button>
        );
      }
      return <a {...props} />;
    },
    code: ({ node, inline, className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || '');
      if (!inline && match && match[1] === 'timeline') {
        return <TimelineWidget jsonStr={String(children).replace(/\n$/, '')} onAction={(msg) => { if (sendMessageRef.current) sendMessageRef.current(msg); }} />;
      }
      return <code className={className} {...props}>{children}</code>;
    }
  }), []);

  useEffect(() => {
      sendMessageRef.current = sendMessage;
  }, [sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const isHero = messages.length === 0;

  return (
    <div className="app-layout">
      <div className="cursor-glow" style={{ left: `${mousePos.x}px`, top: `${mousePos.y}px` }} />

      <div className={`sidebar ${sidebarOpen ? '' : 'compact'} ${animRainbow ? 'rainbow-sidebar' : ''}`} style={{ width: sidebarOpen ? sidebarWidth : 70 }}>
        {sidebarOpen && (
           <div className="sidebar-resizer" onMouseDown={(e) => { e.preventDefault(); setIsResizing(true); }} />
        )}
        <div className="brand">
          <div 
            className="app-logo" 
            style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: sidebarOpen ? "12px" : "0px", width: "100%", justifyContent: sidebarOpen ? "flex-start" : "center" }} 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            onMouseEnter={() => setIsHoveringLogo(true)}
            onMouseLeave={() => setIsHoveringLogo(false)}
          >
            <div className="logo-icon-wrapper shrink-0" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '28px', height: '28px' }}>
              {isHoveringLogo ? (
                sidebarOpen ? <PanelLeftClose size={24} /> : <Sidebar size={24} />
              ) : (
                <img src="/logo.png" alt="A-ware Logo" style={{ height: "28px", width: "auto", objectFit: "contain" }} />
              )}
            </div>
            <span className="hide-on-compact" style={{ fontSize: "1.25rem", fontWeight: 700, whiteSpace: "nowrap" }}>A-ware</span>
          </div>
        </div>

        <button className="new-chat-btn" onClick={startNewSession} title="New Session">
          <Plus size={18} className="shrink-0" /> <span className="hide-on-compact">New Session</span>
        </button>

        <div className="history-list">
          <div className="history-label hide-on-compact">Sessions</div>
          {sessions.slice().sort((a, b) => {
              if (a.is_pinned && !b.is_pinned) return -1;
              if (!a.is_pinned && b.is_pinned) return 1;
              const aTime = a.updated_at || 0;
              const bTime = b.updated_at || 0;
              return bTime - aTime;
          }).map(s => (
            <div key={s.id} className={`history-item ${s.id === currentSessionId ? 'active' : ''} ${s.id === vaporizingSessionId ? 'anim-vaporize' : ''}`} onClick={() => loadSession(s)}>
              <span className="session-icon" onClick={(e) => {
                  if (!sidebarOpen) return;
                  e.stopPropagation();
                  const rect = e.currentTarget.getBoundingClientRect();
                  setEmojiPickerPos({ top: Math.max(10, rect.top - 50), left: rect.right + 10 });
                  setEmojiPickerId(emojiPickerId === s.id ? null : s.id);
                  setActiveMenuId(null);
              }} title="Change Emoji" style={{fontSize: '1.2rem', paddingRight: sidebarOpen ? '8px' : '0px', flexShrink: 0}}>
                {s.emoji || "💬"}
              </span>
              {renamingSessionId === s.id ? (
                <input 
                  autoFocus
                  className="inline-rename-input hide-on-compact"
                  value={renamingText}
                  onChange={e => setRenamingText(e.target.value)}
                  onBlur={() => finishRename(s.id)}
                  onKeyDown={e => e.key === 'Enter' && finishRename(s.id)}
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <span className="history-item-title hide-on-compact">
                  {s.title}
                </span>
              )}
              {s.is_pinned && <Pin size={12} style={{ marginLeft: "auto", marginRight: "5px", color: "#8fa0ba" }} className="hide-on-compact" />}
              {sidebarOpen && renamingSessionId !== s.id && (
                <div className="session-menu-wrapper" onClick={e => e.stopPropagation()}>
                  <button className="dots-btn" onClick={(e) => {
                    e.stopPropagation();
                    if (activeMenuId === s.id) {
                      setActiveMenuId(null);
                    } else {
                      const rect = e.currentTarget.getBoundingClientRect();
                      setMenuPos({ top: rect.top, left: rect.right + 10 });
                      setActiveMenuId(s.id);
                    }
                  }}>
                    <MoreVertical size={16} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="user-profile" style={{ cursor: "pointer" }} onClick={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.getBoundingClientRect();
              setMenuPos({ top: rect.top - 10, left: rect.left });
              setProfileMenuOpen(!profileMenuOpen);
            }}>
            <div className="user-avatar">
              <User size={20} />
            </div>
            <div className="user-info hide-on-compact">
              <span className="user-name">SatyaKesava</span>
              <span className="user-role">Warehouse Admin</span>
            </div>
            
            <div className="hide-on-compact" style={{ marginLeft: "auto", display: "flex", gap: "5px" }}>
                <button 
                  onClick={(e) => { e.stopPropagation(); setAppMode(appMode === "chat" ? "map" : "chat"); }} 
                  style={{ background: "transparent", border: "none", color: appMode === "map" ? "white" : "#8fa0ba", cursor: "pointer", transition: "0.2s", padding: "5px" }}
                  title="Toggle Map View"
                  onMouseEnter={e => e.currentTarget.style.color="white"}
                  onMouseLeave={e => { if(appMode !== "map") e.currentTarget.style.color="#8fa0ba" }}
                >
                  <Map size={18} />
                </button>
            </div>
          </div>
        </div>
      </div>


      {profileMenuOpen && (
        <div className={`dots-dropdown ${animUI ? 'anim-pop' : ''}`} style={{ position: 'fixed', bottom: window.innerHeight - menuPos.top, left: menuPos.left + 10, zIndex: 9999, transformOrigin: 'bottom left' }} onClick={e => e.stopPropagation()}>
          <button onClick={() => { setProfileMenuOpen(false); setSettingsOpen(true); }}><Zap size={16}/> Animations</button>
          <button onClick={() => { setProfileMenuOpen(false); }}><User size={16}/> Log Out</button>
        </div>
      )}

      {activeMenuId && (
        <div className={`dots-dropdown ${animUI ? 'anim-pop' : ''}`} style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, zIndex: 9999, transformOrigin: 'top left' }} onClick={e => e.stopPropagation()}>
          <button onClick={() => {
              const s = sessions.find(s=>s.id===activeMenuId);
              if(s) toggleSessionPin(activeMenuId, !!s.is_pinned);
          }}>
            {sessions.find(s=>s.id===activeMenuId)?.is_pinned ? <PinOff size={16}/> : <Pin size={16}/>}
            {sessions.find(s=>s.id===activeMenuId)?.is_pinned ? "Unpin" : "Pin"}
          </button>
          <button onClick={() => startRename(activeMenuId, sessions.find(s=>s.id===activeMenuId)?.title || "")}><Edit2 size={16}/> Rename</button>
          <button onClick={(e) => {
             const rect = e.currentTarget.getBoundingClientRect();
             setEmojiPickerPos({ top: rect.top, left: rect.right + 10 });
             setEmojiPickerId(activeMenuId);
             setActiveMenuId(null);
          }}><span>😀</span> Change Emoji</button>
          <button onClick={() => { deleteSession(activeMenuId); setActiveMenuId(null); }}><Trash2 size={16}/> Delete</button>
        </div>
      )}

      {emojiPickerId && (
        <div className={`emoji-grid emoji-train ${animUI ? 'anim-pop' : ''}`} style={{ top: emojiPickerPos.top, left: emojiPickerPos.left, transformOrigin: 'top left' }} onClick={e => e.stopPropagation()}>
          {EMOJIS.map(em => (
            <button key={em} className="emoji-btn" onClick={() => changeEmoji(emojiPickerId, em)}>{em}</button>
          ))}
          <input 
            className="emoji-custom-input" 
            placeholder="Custom (e.g. 🐶)"
            value={customEmoji}
            onChange={e => setCustomEmoji(e.target.value)}
            onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') changeEmoji(emojiPickerId, customEmoji); }}
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}

      
      {settingsOpen && (
        <div className="settings-modal-overlay" onClick={() => setSettingsOpen(false)}>
          <div className={`settings-modal ${animUI ? 'anim-pop' : ''}`} onClick={e => e.stopPropagation()}>
            <h2>Animations Profile <button className="settings-close" onClick={() => setSettingsOpen(false)}><X size={18}/></button></h2>
            
            <div className="settings-section" style={{ background: 'rgba(0,0,0,0.2)', padding: '15px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
              <div style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#8fa0ba', letterSpacing: '1px', fontWeight: 'bold' }}>Animation Toggles</div>
              
              <div className="settings-row">
                <span>Text Generation Animation</span>
                <label className="toggle-switch"><input type="checkbox" checked={animText} onChange={e => setAnimText(e.target.checked)} /><span className="slider round"></span></label>
              </div>
              
              <div className="settings-row">
                <span>UI Pop Animations (Apple Style)</span>
                <label className="toggle-switch"><input type="checkbox" checked={animUI} onChange={e => setAnimUI(e.target.checked)} /><span className="slider round"></span></label>
              </div>

              <div className="settings-row">
                <span>Chat Transitions (Slide & Fade)</span>
                <label className="toggle-switch"><input type="checkbox" checked={animChatOpen} onChange={e => setAnimChatOpen(e.target.checked)} /><span className="slider round"></span></label>
              </div>

              <div className="settings-row">
                <span>Vaporize Delete Effect</span>
                <label className="toggle-switch"><input type="checkbox" checked={animDeleteChat} onChange={e => setAnimDeleteChat(e.target.checked)} /><span className="slider round"></span></label>
              </div>

              <div className="settings-row">
                <span>Rainbow Sidebar Glow</span>
                <label className="toggle-switch"><input type="checkbox" checked={animRainbow} onChange={e => setAnimRainbow(e.target.checked)} /><span className="slider round"></span></label>
              </div>
            </div>

            <div className="settings-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '10px' }}>
              <span>Animation Speed ({animSpeed}s)</span>
              <input type="range" min="0.1" max="1.0" step="0.1" value={animSpeed} onChange={e => setAnimSpeed(parseFloat(e.target.value))} style={{ width: '100%' }} />
            </div>

            <button onClick={() => { setAnimText(true); setAnimUI(true); setAnimChatOpen(true); setAnimDeleteChat(true); setAnimRainbow(false); setAnimSpeed(0.3); }} style={{ background: 'rgba(255,255,255,0.1)', color: 'white', border: 'none', padding: '10px', borderRadius: '8px', cursor: 'pointer', marginTop: '10px' }}>
              Reset Default Animations
            </button>
          </div>
        </div>
      )}

      {sessionToDelete && (
        <div className="settings-modal-overlay" onClick={() => setSessionToDelete(null)}>
          <div className={`settings-modal ${animUI ? 'anim-pop' : ''}`} onClick={e => e.stopPropagation()} style={{ textAlign: "center", maxWidth: "300px" }}>
            <h3 style={{ margin: "0 0 10px 0", color: "#ff595e" }}>Delete Session</h3>
            <p style={{ color: "#8fa0ba", fontSize: "0.95rem", marginBottom: "24px" }}>Are you completely sure you want to delete this chat? This cannot be undone.</p>
            <div style={{ display: "flex", gap: "12px", justifyItems: "stretch" }}>
              <button onClick={() => setSessionToDelete(null)} style={{ flex: 1, padding: "10px", borderRadius: "8px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "white", cursor: "pointer", transition: "0.2s" }} onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,0.1)"} onMouseLeave={e=>e.currentTarget.style.background="rgba(255,255,255,0.05)"}>Cancel</button>
              <button onClick={() => confirmDelete(sessionToDelete)} style={{ flex: 1, padding: "10px", borderRadius: "8px", background: "#ff595e", border: "none", color: "white", cursor: "pointer", fontWeight: "600", transition: "0.2s" }} onMouseEnter={e=>e.currentTarget.style.background="#ff3a40"} onMouseLeave={e=>e.currentTarget.style.background="#ff595e"}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div key={chatKey} className={`main-area ${animChatOpen ? 'anim-slide-in' : ''}`} style={{ paddingLeft: sidebarOpen ? sidebarWidth : 70 }}>
        {appMode === "map" ? (
           <WarehouseMap animUI={animUI} allowChanges={allowChanges} setAllowChanges={setAllowChanges} onAgentInteraction={async (q, r) => {
             const userMsg: Message = { role: "user", content: q };
             const botMsg: Message = { role: "assistant", content: r };
             const finalMsgs = [...messages, userMsg, botMsg];
             setMessages(finalMsgs);
             const st = sessions.find(s => s.id === currentSessionId)?.title || "New Session";
             await saveCurrentSessionToDB(currentSessionId, st, finalMsgs, imageQueue);
           }} />
        ) : (
          <>
            <div className="top-bar">
          <div className="top-bar-left"></div>
          <div className="top-bar-right" style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
             <div className="context-manager-wrapper" style={{ display: 'inline-block' }}>
               <button className="top-bar-btn context-btn" onClick={() => setPopoutOpen(!popoutOpen)}>
                 <span className="context-badge">{imageQueue.length}/5</span>
                 <span className="hide-on-mobile">Context Quota</span>
               </button>
               {popoutOpen && (
                 <div className={`context-popout ${animUI ? 'anim-pop' : ''}`} style={{ top: '100%', bottom: 'auto', marginTop: '10px', right: 0, left: 'auto', transformOrigin: 'top right' }}>
                   <div className="context-popout-header">
                     <span>Image Context Queue</span>
                     <button className="context-popout-close" onClick={() => setPopoutOpen(false)}><X size={16} /></button>
                   </div>
                   {imageQueue.length === 0 ? (
                     <div style={{ color: '#8fa0ba', fontSize: '0.8rem', textAlign: 'center', padding: '10px 0' }}>No images in context</div>
                   ) : (
                     <div className="context-image-list">
                       {imageQueue.map((q, idx) => (
                         <div key={q.id} className="context-image-item" style={{ opacity: q.isSelected ? 1 : 0.5 }}>
                           <img src={q.base64} alt={`Image ${idx+1}`} className="context-image-thumb" />
                           <div className="context-image-info">
                             <span className="context-image-title">Image {idx + 1}</span>
                             <div className="context-actions">
                               <button className={`context-action-btn ${q.isSelected ? 'active' : ''}`} onClick={() => toggleSelect(q.id)} title="Toggle Use Context">
                                 {q.isSelected ? <CheckSquare size={14} /> : <Square size={14} />}
                               </button>
                               <button className={`context-action-btn ${q.isPinned ? 'active-pin' : ''}`} onClick={() => togglePin(q.id)} title="Pin in Queue">
                                 <Pin size={14} />
                               </button>
                             </div>
                           </div>
                         </div>
                       ))}
                     </div>
                   )}
                 </div>
               )}
             </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <label className="toggle-switch" title="Bypass LLM vision and rely ONLY on YOLO detections">
                <input type="checkbox" checked={yoloBypass} onChange={(e) => setYoloBypass(e.target.checked)} />
                <span className="slider round"></span>
                <span className="toggle-label"><Zap size={14} color="#ffca3a" /> YOLO Bypass</span>
              </label>
              <label className="toggle-switch" title="Allow the agent to modify the SQL inventory database">
                <input type="checkbox" checked={allowChanges} onChange={(e) => setAllowChanges(e.target.checked)} />
                <span className="slider round" style={allowChanges ? { backgroundColor: '#ef476f' } : {}}></span>
                <span className="toggle-label"><CheckSquare size={14} color={allowChanges ? '#ef476f' : '#888'} /> Allow Changes</span>
              </label>
            </div>
          </div>
        </div>

        {isHero ? (
          <div className="hero-container">
            <h1 className="hero-title">Hi SatyaKesava, how can I assist you today?</h1>
            <div className="rainbow-wrapper">
              <div className="input-box">
                {previews.length > 0 && (
                  <div className="upload-preview">
                    {previews.map((src, i) => (
                      <div key={i} className="upload-preview-item">
                        <img src={src} alt="preview" />
                        <button className="upload-remove-btn" onClick={() => removeFile(i)}><X size={12} /></button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="input-row">
                  <label className="btn-icon" title="Upload Image">
                    <ImagePlus size={22} />
                    <input type="file" accept="image/*" multiple onChange={handleFileSelect} style={{ display: "none" }} />
                  </label>
                  <textarea
                    className="input-field"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    placeholder="Ask A-Ware..."
                    rows={1}
                    style={{ height: input.split('\n').length > 1 ? `${Math.min(input.split('\n').length * 24, 200)}px` : "auto" }}
                  />
                  <button className="btn-send" onClick={() => sendMessage()} disabled={isLoading || (!input.trim() && selectedFiles.length === 0)}>
                    <Send size={18} />
                  </button>
                  <button className="btn-send" onClick={() => setIsVoiceMode(true)} style={{ marginLeft: "8px" }} title="Start Voice Mode">
                    <Mic size={18} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="chat-container">
              <div className="chat-messages">
                {messages.map((m, idx) => {
                  const isLastUser = m.role === "user" && idx === messages.length - 1 || (m.role === "user" && messages[idx+1]?.role === "assistant" && idx === messages.length - 2);
                  
                  return (
                  <div key={idx} className={`message-row ${m.role}`}>
                    <div className="message-bubble group">
                      {m.images && (
                        <div className="image-gallery">
                          {m.images.map((img, i) => (
                            <img key={i} src={img} alt="attachment" className="image-preview" />
                          ))}
                        </div>
                      )}
                      
                      {m.thinking && <ThinkingBlock text={m.thinking} animUI={animUI} />}
                      
                      {m.isTyping && m.role === "assistant" && animText ? (
                        <Typewriter text={m.content} onComplete={() => {
                          const newMessages = [...messages];
                          newMessages[idx].isTyping = false;
                          setMessages(newMessages);
                        }} onAction={(label) => sendMessage(label)} />
                      ) : (
                        <ReactMarkdown components={markdownComponents}>{m.content}</ReactMarkdown>
                      )}
                      
                      {/* Hover Actions */}
                      <div className="message-actions">
                        {!m.isTyping && (
                          <button className="msg-action-btn" onClick={() => copyToClipboard(m.content)} title="Copy">
                            <Copy size={14} />
                          </button>
                        )}
                        {m.role === "user" && isLastUser && (
                          <button className="msg-action-btn" onClick={() => editMessage(idx)} title="Edit Query">
                            <Edit2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )})}
                {isLoading && (
                  <div className="message-row assistant">
                    <div className="message-bubble" style={{ display: "flex", gap: "10px", alignItems: "center", color: "#8fa0ba" }}>
                      {loadingStatus.toLowerCase().includes('sql') ? <Database className="animate-pulse" size={18} /> :
                       loadingStatus.toLowerCase().includes('rout') ? <Network className="animate-pulse" size={18} /> :
                       loadingStatus.toLowerCase().includes('generat') ? <Sparkles className="animate-pulse" size={18} /> :
                       loadingStatus.toLowerCase().includes('think') ? <Brain className="animate-pulse" size={18} /> :
                       <Loader2 className="animate-spin" size={18} />}
                      {loadingStatus || "Loading..."}
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="input-wrapper">
              <div className="input-box">
                {previews.length > 0 && (
                  <div className="upload-preview">
                    {previews.map((src, i) => (
                      <div key={i} className="upload-preview-item">
                        <img src={src} alt="preview" />
                        <button className="upload-remove-btn" onClick={() => removeFile(i)}><X size={12} /></button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="input-row">
                  <label className="btn-icon" title="Upload Image">
                    <ImagePlus size={22} />
                    <input type="file" accept="image/*" multiple onChange={handleFileSelect} style={{ display: "none" }} />
                  </label>
                  <textarea
                    className="input-field"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    placeholder="Ask A-Ware..."
                    rows={1}
                    style={{ height: input.split('\n').length > 1 ? `${Math.min(input.split('\n').length * 24, 200)}px` : "auto" }}
                  />
                  {isLoading ? (
                      <button className="btn-send" onClick={abortQuery} style={{ background: "rgba(255,89,94,0.2)", color: "#ff595e" }} title="Stop Generating">
                        <Square size={18} fill="currentColor" />
                      </button>
                  ) : (
                      <button className="btn-send" onClick={() => sendMessage()} disabled={!input.trim() && selectedFiles.length === 0}>
                        <Send size={18} />
                      </button>
                  )}
                  <button className="btn-send" onClick={() => setIsVoiceMode(true)} style={{ marginLeft: "8px" }} title="Start Voice Mode">
                    <Mic size={18} />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
        </>
        )}
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
                  if (isLoading) abortQuery();
                  interrupt();
              }
          }} />
        </div>
      )}
    </div>
  );
}

function ThinkingBlock({ text, animUI }: { text: string, animUI: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="thinking-block">
      <div className="thinking-summary" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        Thought Process
      </div>
      {open && (
        <div className={`thinking-content ${animUI ? 'anim-fade-rise' : ''}`} style={{ transformOrigin: 'top left' }}>
          <ReactMarkdown>{text}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
