"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2poalNRPT06ZTYxYmZkZjk=

import * as React from "react";
import { Bell, User, LogOut, Settings, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { LanguageSelector } from "./language-selector";
import { useLanguage } from "@/providers/LanguageProvider";
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2poalNRPT06ZTYxYmZkZjk=

interface HeaderProps {
  title?: string;
  children?: React.ReactNode;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2poalNRPT06ZTYxYmZkZjk=

export function Header({ title, children }: HeaderProps) {
  const { t } = useLanguage();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div className="flex items-center gap-4">
        {title && <h1 className="text-lg font-semibold">{title}</h1>}
        {children}
      </div>

      <div className="flex items-center gap-2">
        {/* Notifications */}
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>

        {/* Help */}
        <Button variant="ghost" size="icon">
          <HelpCircle className="h-5 w-5" />
        </Button>

        {/* Language Selector */}
        <LanguageSelector />

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-8 w-8 rounded-full">
              <Avatar className="h-8 w-8">
                <AvatarImage src="/avatar.svg" alt={t("header.testUser")} />
                <AvatarFallback>
                  <User className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end" forceMount>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">{t("header.testUser")}</p>
                <p className="text-xs leading-none text-muted-foreground">
                  test@example.com
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <User className="mr-2 h-4 w-4" />
              <span>{t("header.userProfile")}</span>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Settings className="mr-2 h-4 w-4" />
              <span>{t("nav.settings")}</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              <span>{t("header.logout")}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2poalNRPT06ZTYxYmZkZjk=

