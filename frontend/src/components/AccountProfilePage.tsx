"use client";

import { FormEvent, useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import LoadingState from "@/components/LoadingState";
import { useMongoStorage } from "@/lib/database-storage";
import {
  changeUserPassword,
  fetchCurrentUser,
  updateUserProfile,
  uploadUserAvatar,
} from "@/lib/auth-session";
import { createClient } from "@/lib/supabase";

const AVATAR_BUCKET = "avatars";
const MAX_AVATAR_SOURCE_SIZE = 12 * 1024 * 1024;
const MAX_AVATAR_UPLOAD_SIZE = 2 * 1024 * 1024;
const AVATAR_MAX_DIMENSION = 512;
const DIRECT_AVATAR_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);

type ProfileState = {
  id: string;
  email: string;
  role: string;
  displayName: string;
  avatarUrl: string;
};

function initials(value: string) {
  return (
    value
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "A"
  );
}

function readDisplayName(metadata?: Record<string, unknown>, email?: string) {
  const name = metadata?.display_name;
  if (typeof name === "string" && name.trim()) return name.trim();
  if (email) return email.split("@")[0] || "User";
  return "User";
}

function readAvatarUrl(metadata?: Record<string, unknown>) {
  const url = metadata?.avatar_url;
  return typeof url === "string" ? url : "";
}

function notifyProfileUpdated(detail: unknown) {
  window.dispatchEvent(new CustomEvent("account-profile-updated", { detail }));
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Could not read avatar image."));
    image.src = src;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error("Could not prepare avatar image."));
      },
      type,
      quality
    );
  });
}

async function prepareAvatarFile(file: File) {
  if (file.size <= MAX_AVATAR_UPLOAD_SIZE && DIRECT_AVATAR_MIME_TYPES.has(file.type)) {
    return file;
  }

  const previewUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(previewUrl);
    const scale = Math.min(
      1,
      AVATAR_MAX_DIMENSION / Math.max(image.naturalWidth || image.width, image.naturalHeight || image.height)
    );
    const width = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
    const height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not prepare avatar image.");
    context.drawImage(image, 0, 0, width, height);

    for (const quality of [0.88, 0.78, 0.68, 0.58]) {
      const blob = await canvasToBlob(canvas, "image/webp", quality);
      if (blob.size <= MAX_AVATAR_UPLOAD_SIZE) {
        return new File([blob], "avatar.webp", { type: "image/webp" });
      }
    }

    const fallback = await canvasToBlob(canvas, "image/jpeg", 0.62);
    if (fallback.size <= MAX_AVATAR_UPLOAD_SIZE) {
      return new File([fallback], "avatar.jpg", { type: "image/jpeg" });
    }
  } finally {
    URL.revokeObjectURL(previewUrl);
  }

  throw new Error("This image is too large. Please choose a smaller image.");
}

function fromMongoUser(user: {
  id: string;
  email?: string;
  role?: string;
  user_metadata?: Record<string, unknown>;
}): ProfileState {
  const metadata = user.user_metadata || {};
  return {
    id: user.id,
    email: user.email || "",
    role: user.role || "admin",
    displayName: readDisplayName(metadata, user.email),
    avatarUrl: readAvatarUrl(metadata),
  };
}

function fromSupabaseUser(user: User): ProfileState {
  const metadata = user.user_metadata || {};
  return {
    id: user.id,
    email: user.email || "",
    role: String(user.app_metadata?.role || "admin"),
    displayName: readDisplayName(metadata, user.email),
    avatarUrl: readAvatarUrl(metadata),
  };
}

export default function AccountProfilePage() {
  const [profile, setProfile] = useState<ProfileState | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadProfile() {
    setLoading(true);
    setError("");

    try {
      if (useMongoStorage) {
        const user = await fetchCurrentUser();
        if (!user) {
          setProfile(null);
          setError("Could not load profile.");
          return;
        }
        const next = fromMongoUser(user);
        setProfile(next);
        setDisplayName(next.displayName);
        setAvatarUrl(next.avatarUrl);
        return;
      }

      const supabase = createClient();
      const { data, error: userError } = await supabase.auth.getUser();
      if (userError || !data.user) {
        setProfile(null);
        setError(userError?.message || "Could not load profile.");
        return;
      }
      const next = fromSupabaseUser(data.user);
      setProfile(next);
      setDisplayName(next.displayName);
      setAvatarUrl(next.avatarUrl);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProfile();
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;

    const cleanName = displayName.trim();
    if (!cleanName) {
      setError("Display name is required.");
      return;
    }

    setSaving(true);
    setError("");
    setMessage("");

    try {
      if (useMongoStorage) {
        const updated = await updateUserProfile({ display_name: cleanName });
        const next = fromMongoUser(updated);
        setProfile(next);
        setDisplayName(next.displayName);
        notifyProfileUpdated({
          id: next.id,
          email: next.email,
          user_metadata: updated.user_metadata || {},
          app_metadata: { role: next.role },
        });
        setMessage("Profile saved.");
        return;
      }

      const supabase = createClient();
      const { data, error: updateError } = await supabase.auth.updateUser({
        data: {
          display_name: cleanName,
          name: cleanName,
          avatar_url: avatarUrl,
        },
      });
      if (updateError || !data.user) {
        throw new Error(updateError?.message || "Could not update profile.");
      }
      const next = fromSupabaseUser(data.user);
      setProfile(next);
      setDisplayName(next.displayName);
      setAvatarUrl(next.avatarUrl);
      notifyProfileUpdated(data.user);
      setMessage("Profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update profile.");
    } finally {
      setSaving(false);
    }
  }

  async function uploadAvatar(file?: File) {
    if (!profile || !file) return;
    setError("");
    setMessage("");

    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }
    if (file.size > MAX_AVATAR_SOURCE_SIZE) {
      setError("Image must be 12 MB or smaller.");
      return;
    }

    setUploadingAvatar(true);
    const previewUrl = URL.createObjectURL(file);
    setAvatarUrl(previewUrl);

    try {
      const prepared = await prepareAvatarFile(file);

      if (useMongoStorage) {
        const result = await uploadUserAvatar(prepared);
        const nextUrl = result.avatar_url || "";
        URL.revokeObjectURL(previewUrl);
        setAvatarUrl(nextUrl);
        const refreshed = await fetchCurrentUser();
        if (refreshed) {
          const next = fromMongoUser(refreshed);
          setProfile(next);
          notifyProfileUpdated({
            id: next.id,
            email: next.email,
            user_metadata: refreshed.user_metadata || {},
            app_metadata: { role: next.role },
          });
        }
        setMessage("Avatar updated.");
        return;
      }

      const supabase = createClient();
      const ext = prepared.name.split(".").pop()?.toLowerCase() || "webp";
      const path = `${profile.id}/avatar.${ext}`;
      const { error: uploadError } = await supabase.storage
        .from(AVATAR_BUCKET)
        .upload(path, prepared, { cacheControl: "3600", contentType: prepared.type, upsert: true });

      if (uploadError) {
        throw new Error(uploadError.message);
      }

      const { data: publicData } = supabase.storage.from(AVATAR_BUCKET).getPublicUrl(path);
      const publicUrl = `${publicData.publicUrl}?v=${Date.now()}`;
      const { data, error: updateError } = await supabase.auth.updateUser({
        data: { avatar_url: publicUrl },
      });
      URL.revokeObjectURL(previewUrl);
      if (updateError || !data.user) {
        throw new Error(updateError?.message || "Avatar uploaded, but profile could not be updated.");
      }
      const next = fromSupabaseUser(data.user);
      setProfile(next);
      setAvatarUrl(next.avatarUrl);
      notifyProfileUpdated(data.user);
      setMessage("Avatar updated.");
    } catch (err) {
      URL.revokeObjectURL(previewUrl);
      setAvatarUrl(profile.avatarUrl);
      setError(err instanceof Error ? err.message : "Could not upload avatar.");
    } finally {
      setUploadingAvatar(false);
    }
  }

  async function removeAvatar() {
    if (!profile || !avatarUrl) return;
    setError("");
    setMessage("");
    setUploadingAvatar(true);

    try {
      if (useMongoStorage) {
        await updateUserProfile({ avatar_url: "" });
        setAvatarUrl("");
        const refreshed = await fetchCurrentUser();
        if (refreshed) {
          const next = fromMongoUser(refreshed);
          setProfile(next);
          notifyProfileUpdated({
            id: next.id,
            email: next.email,
            user_metadata: refreshed.user_metadata || {},
            app_metadata: { role: next.role },
          });
        }
        setMessage("Avatar removed.");
        return;
      }

      const supabase = createClient();
      const { data, error: updateError } = await supabase.auth.updateUser({
        data: { avatar_url: "" },
      });
      if (updateError || !data.user) {
        throw new Error(updateError?.message || "Could not remove avatar.");
      }
      const next = fromSupabaseUser(data.user);
      setProfile(next);
      setAvatarUrl("");
      notifyProfileUpdated(data.user);
      setMessage("Avatar removed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove avatar.");
    } finally {
      setUploadingAvatar(false);
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;

    const current = currentPassword;
    const next = newPassword.trim();
    const confirm = confirmPassword.trim();

    if (!current) {
      setError("Enter your current password.");
      return;
    }
    if (next.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }

    setChangingPassword(true);
    setError("");
    setMessage("");

    try {
      if (useMongoStorage) {
        await changeUserPassword(current, next);
        setMessage("Password updated.");
      } else {
        const supabase = createClient();
        const { error: verifyError } = await supabase.auth.signInWithPassword({
          email: profile.email,
          password: current,
        });
        if (verifyError) {
          throw new Error("Current password is incorrect.");
        }
        const { error: updateError } = await supabase.auth.updateUser({ password: next });
        if (updateError) {
          throw new Error(updateError.message);
        }
        setMessage("Password updated.");
      }
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password.");
    } finally {
      setChangingPassword(false);
    }
  }

  if (loading) {
    return <LoadingState variant="page" title="Loading profile" detail="Reading your account settings." />;
  }

  if (!profile) {
    return (
      <div className="account-profile account-profile--simple">
        <p className="alert-error">{error || "Could not load profile."}</p>
      </div>
    );
  }

  const label = displayName.trim() || profile.displayName;

  return (
    <div className="account-profile account-profile--simple">
      <header className="account-profile-page-head">
        <h1>Profile</h1>
        <p>Update your display name, avatar, and password.</p>
      </header>

      {error ? <p className="alert-error">{error}</p> : null}
      {message ? <p className="alert-success">{message}</p> : null}

      <section className="account-profile-card">
        <form className="account-profile-form" onSubmit={saveProfile}>
          <div className="account-profile-avatar-editor">
            <div className="account-profile-avatar account-profile-avatar--editor" aria-hidden="true">
              {avatarUrl ? <img src={avatarUrl} alt="" /> : initials(label)}
            </div>
            <div className="account-profile-avatar-editor__actions">
              <label className="btn-secondary">
                {uploadingAvatar ? "Uploading…" : "Change photo"}
                <input
                  type="file"
                  accept="image/*"
                  disabled={uploadingAvatar || saving}
                  onChange={(event) => {
                    void uploadAvatar(event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </label>
              {avatarUrl ? (
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={uploadingAvatar || saving}
                  onClick={() => void removeAvatar()}
                >
                  Remove
                </button>
              ) : null}
            </div>
          </div>

          <label>
            <span>Display name</span>
            <input
              className="input"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="How your name appears in the console"
              autoComplete="nickname"
              required
            />
          </label>

          <label>
            <span>Email</span>
            <input className="input account-profile-readonly" value={profile.email} readOnly disabled />
          </label>

          <div className="account-profile-form-actions">
            <button type="submit" className="btn-primary" disabled={saving || uploadingAvatar}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </section>

      <section className="account-profile-card">
        <div className="account-profile-section-head">
          <span>Security</span>
          <strong>Change password</strong>
        </div>
        <form className="account-profile-form" onSubmit={savePassword}>
          <label>
            <span>Current password</span>
            <input
              className="input"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              disabled={changingPassword || saving || uploadingAvatar}
            />
          </label>
          <label>
            <span>New password</span>
            <input
              className="input"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={6}
              disabled={changingPassword || saving || uploadingAvatar}
            />
          </label>
          <label>
            <span>Confirm new password</span>
            <input
              className="input"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={6}
              disabled={changingPassword || saving || uploadingAvatar}
            />
          </label>
          <div className="account-profile-form-actions">
            <button
              type="submit"
              className="btn-primary"
              disabled={changingPassword || saving || uploadingAvatar}
            >
              {changingPassword ? "Updating…" : "Update password"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
