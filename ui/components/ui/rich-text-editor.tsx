"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjNrelN3PT06MTdiZGM3NWY=

import * as React from "react";
import {
  Bold,
  Italic,
  Underline,
  Strikethrough,
  Code,
  List,
  ListOrdered,
  Table,
  Link,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjNrelN3PT06MTdiZGM3NWY=

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
  id?: string;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjNrelN3PT06MTdiZGM3NWY=

interface ToolbarButton {
  icon: React.ElementType;
  label: string;
  action: () => void;
  shortcut?: string;
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjNrelN3PT06MTdiZGM3NWY=

export function RichTextEditor({
  value,
  onChange,
  placeholder,
  rows = 3,
  className,
  id,
}: RichTextEditorProps) {
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  // 在光标位置插入文本
  const insertText = (before: string, after: string = "") => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);
    const newText =
      value.substring(0, start) +
      before +
      selectedText +
      after +
      value.substring(end);

    onChange(newText);

    // 恢复焦点和光标位置
    setTimeout(() => {
      textarea.focus();
      const newCursorPos = start + before.length + selectedText.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  };

  // 包裹选中文本
  const wrapSelection = (wrapper: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);

    if (selectedText) {
      const newText =
        value.substring(0, start) +
        wrapper +
        selectedText +
        wrapper +
        value.substring(end);
      onChange(newText);
    } else {
      insertText(wrapper, wrapper);
    }
  };

  const toolbarButtons: ToolbarButton[] = [
    {
      icon: Bold,
      label: "粗体",
      action: () => wrapSelection("**"),
      shortcut: "Ctrl+B",
    },
    {
      icon: Italic,
      label: "斜体",
      action: () => wrapSelection("*"),
      shortcut: "Ctrl+I",
    },
    {
      icon: Underline,
      label: "下划线",
      action: () => wrapSelection("__"),
      shortcut: "Ctrl+U",
    },
    {
      icon: Strikethrough,
      label: "删除线",
      action: () => wrapSelection("~~"),
    },
    {
      icon: Code,
      label: "代码",
      action: () => wrapSelection("`"),
    },
    {
      icon: ListOrdered,
      label: "有序列表",
      action: () => insertText("1. "),
    },
    {
      icon: List,
      label: "无序列表",
      action: () => insertText("- "),
    },
    {
      icon: Table,
      label: "表格",
      action: () =>
        insertText("| 列1 | 列2 |\n| --- | --- |\n| 内容 | 内容 |"),
    },
    {
      icon: Link,
      label: "链接",
      action: () => insertText("[链接文本](", ")"),
    },
  ];

  // 键盘快捷键
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey) {
      switch (e.key.toLowerCase()) {
        case "b":
          e.preventDefault();
          wrapSelection("**");
          break;
        case "i":
          e.preventDefault();
          wrapSelection("*");
          break;
        case "u":
          e.preventDefault();
          wrapSelection("__");
          break;
      }
    }
  };

  return (
    <div className={cn("rounded-md border", className)}>
      {/* 工具栏 */}
      <div className="flex flex-wrap items-center gap-0.5 border-b bg-muted/30 p-1">
        <TooltipProvider delayDuration={300}>
          {toolbarButtons.map((button, index) => (
            <Tooltip key={index}>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={(e) => {
                    e.preventDefault();
                    button.action();
                  }}
                >
                  <button.icon className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p>
                  {button.label}
                  {button.shortcut && (
                    <span className="ml-2 text-muted-foreground">
                      ({button.shortcut})
                    </span>
                  )}
                </p>
              </TooltipContent>
            </Tooltip>
          ))}
        </TooltipProvider>
      </div>

      {/* 编辑区域 */}
      <Textarea
        ref={textareaRef}
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={rows}
        className="resize-none rounded-none border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
      />
    </div>
  );
}

