import re

def update_page():
    with open("frontend/src/app/page.tsx", "r", encoding="utf-8") as f:
        content = f.read()

    # Add state
    if "const [allowChanges, setAllowChanges] = useState(false);" not in content:
        content = content.replace(
            "const [yoloBypass, setYoloBypass] = useState(false);",
            "const [yoloBypass, setYoloBypass] = useState(false);\n  const [allowChanges, setAllowChanges] = useState(false);"
        )

    # Add form data
    if "formData.append(\"allow_changes\", allowChanges.toString());" not in content:
        content = content.replace(
            "formData.append(\"use_yolo_only\", yoloBypass.toString());",
            "formData.append(\"use_yolo_only\", yoloBypass.toString());\n      formData.append(\"allow_changes\", allowChanges.toString());"
        )

    # Add UI toggle
    old_ui = """            <label className="toggle-switch" title="Bypass LLM vision and rely ONLY on YOLO detections">
              <input type="checkbox" checked={yoloBypass} onChange={(e) => setYoloBypass(e.target.checked)} />
              <span className="slider round"></span>
              <span className="toggle-label"><Zap size={14} color="#ffca3a" /> YOLO Bypass</span>
            </label>"""
            
    new_ui = """            <div style={{ display: 'flex', gap: '16px' }}>
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
            </div>"""

    if "Allow Changes" not in content:
        content = content.replace(old_ui, new_ui)

    with open("frontend/src/app/page.tsx", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_page()
    print("Frontend page.tsx updated successfully.")
