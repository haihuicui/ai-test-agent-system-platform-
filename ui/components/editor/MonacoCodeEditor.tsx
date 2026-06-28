/**
 * Monaco Code Editor 组件
 *
 * 使用 Monaco Editor (VS Code 的编辑器核心) 提供专业的代码编辑体验
 */
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhSdVRRPT06NjkzNmU0OTI=

"use client";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhSdVRRPT06NjkzNmU0OTI=

import React, { useRef, useEffect } from "react";
import Editor, { OnMount, OnChange } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhSdVRRPT06NjkzNmU0OTI=

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language: string;
  readOnly?: boolean;
  height?: string;
  minimap?: boolean;
  fontSize?: number;
  onSave?: () => void;
}

export function MonacoCodeEditor({
  value,
  onChange,
  language,
  readOnly = false,
  height = "500px",
  minimap = false,
  fontSize = 14,
  onSave,
}: CodeEditorProps) {
  const editorRef = useRef<any>(null);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // 添加保存快捷键 (Ctrl+S / Cmd+S)
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (onSave) {
        onSave();
      }
      return null;
    });

    // 确保编辑器在挂载后立即布局
    setTimeout(() => {
      editor.layout();
    }, 100);
  };

  const handleChange: OnChange = (value) => {
    onChange(value || "");
  };

  return (
    <div className="border-0 rounded-lg overflow-hidden shadow-sm h-full">
      <Editor
        height={height}
        language={language}
        value={value}
        onChange={handleChange}
        onMount={handleEditorDidMount}
        theme="vs"
        options={{
          readOnly,
          minimap: { enabled: minimap },
          fontSize,
          lineHeight: 20,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
          fontLigatures: true,
          tabSize: 2,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: "on",
          formatOnPaste: true,
          formatOnType: true,
        }}
      />
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhSdVRRPT06NjkzNmU0OTI=
