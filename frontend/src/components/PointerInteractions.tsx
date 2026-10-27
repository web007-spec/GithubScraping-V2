"use client";

import { useEffect } from "react";

const MOTION_SELECTOR = [
  "button",
  "a",
  "input",
  "select",
  "textarea",
  ".card",
  ".card-muted",
  ".app-account-trigger",
  ".app-account-dropdown a",
  ".app-account-dropdown button",
  ".dashboard-hero",
  ".dashboard-card",
  ".dashboard-hero__panel",
  ".dashboard-mini",
  ".dashboard-selected-country",
  ".dashboard-country-row",
  ".dashboard-action",
  ".account-profile-hero",
  ".account-profile-card",
  ".profile-hero",
  ".profile-card",
  ".profile-stat",
  ".loading-state",
].join(",");

const DASHBOARD_DRAG_SELECTOR = [
  ".dashboard-card",
  ".dashboard-hero",
  ".dashboard-hero__panel",
  ".dashboard-mini",
  ".dashboard-selected-country",
  ".dashboard-country-row",
  ".dashboard-action",
  ".dashboard-page button",
  ".dashboard-page a",
  ".dashboard-page h1",
  ".dashboard-page h2",
  ".dashboard-page p",
  ".dashboard-page span",
  ".dashboard-page strong",
].join(",");

const DASHBOARD_PART_SELECTOR = [
  ".dashboard-hero",
  ".dashboard-card",
].join(",");

function isFormControl(element: Element) {
  return ["INPUT", "SELECT", "TEXTAREA", "OPTION"].includes(element.tagName);
}

function isDisabled(element: HTMLElement) {
  return (
    element.hasAttribute("disabled") ||
    element.getAttribute("aria-disabled") === "true" ||
    element.classList.contains("disabled")
  );
}

function canReceiveClickMotion(element: HTMLElement) {
  if (element.closest(".ag-material-demo, .chat-app, .chat-page, .ag-root")) return false;
  return !["HTML", "BODY", "SCRIPT", "STYLE", "META", "LINK", "OPTION"].includes(
    element.tagName
  );
}

export default function PointerInteractions() {
  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let activeElement: HTMLElement | null = null;
    let dragCandidate:
      | {
          element: HTMLElement;
          pointerId: number;
          startX: number;
          startY: number;
          dragging: boolean;
          swapTarget: HTMLElement | null;
        }
      | null = null;
    let suppressNextClick = false;

    function isInsideStableGrid(target: EventTarget | null) {
      return target instanceof Element && !!target.closest(".ag-material-demo");
    }

    function isInsideChat(target: EventTarget | null) {
      return target instanceof Element && !!target.closest(".chat-app, .chat-page");
    }

    function findTarget(target: EventTarget | null) {
      if (isInsideStableGrid(target) || isInsideChat(target)) return null;
      if (!(target instanceof Element)) return null;
      const element = target.closest(MOTION_SELECTOR);
      if (!(element instanceof HTMLElement) || isDisabled(element)) return null;
      return element;
    }

    function findClickTarget(target: EventTarget | null) {
      if (isInsideStableGrid(target) || isInsideChat(target)) return null;
      const preferred = findTarget(target);
      if (preferred) return preferred;
      if (!(target instanceof Element)) return null;
      const element = target.closest("*");
      if (!(element instanceof HTMLElement) || !canReceiveClickMotion(element)) return null;
      return element;
    }

    function findDashboardDragTarget(target: EventTarget | null) {
      if (reducedMotion.matches || isInsideStableGrid(target)) return null;
      if (!(target instanceof Element)) return null;
      if (!target.closest(".dashboard-page")) return null;
      if (target.closest("input, select, textarea, option")) return null;
      const part = target.closest(DASHBOARD_PART_SELECTOR);
      if (part instanceof HTMLElement && !isDisabled(part)) return part;
      const element = target.closest(DASHBOARD_DRAG_SELECTOR);
      if (!(element instanceof HTMLElement) || isDisabled(element)) return null;
      return element;
    }

    function findSwapTargetAtPoint(x: number, y: number) {
      if (!dragCandidate) return null;
      const dragged = dragCandidate.element;
      const previousPointerEvents = dragged.style.pointerEvents;
      dragged.style.pointerEvents = "none";
      const elementAtPoint = document.elementFromPoint(x, y);
      dragged.style.pointerEvents = previousPointerEvents;
      if (!(elementAtPoint instanceof Element)) return null;
      const target = findDashboardDragTarget(elementAtPoint);
      if (!target || target === dragged) return null;
      if (dragged.contains(target) || target.contains(dragged)) return null;
      return target;
    }

    function setSwapTarget(target: HTMLElement | null) {
      if (!dragCandidate) return;
      if (dragCandidate.swapTarget === target) return;
      dragCandidate.swapTarget?.classList.remove("dashboard-drag-over");
      dragCandidate.swapTarget = target;
      target?.classList.add("dashboard-drag-over");
    }

    function swapElements(a: HTMLElement, b: HTMLElement) {
      const aParent = a.parentNode;
      const bParent = b.parentNode;
      if (!aParent || !bParent) return;
      if (a.contains(b) || b.contains(a)) return;
      const aMarker = document.createTextNode("");
      const bMarker = document.createTextNode("");
      aParent.insertBefore(aMarker, a);
      bParent.insertBefore(bMarker, b);
      aMarker.parentNode?.replaceChild(b, aMarker);
      bMarker.parentNode?.replaceChild(a, bMarker);
    }

    function clearActive(element: HTMLElement | null) {
      if (!element) return;
      element.classList.remove("motion-active");
      element.style.removeProperty("--pointer-x");
      element.style.removeProperty("--pointer-y");
      element.style.removeProperty("--tilt-x");
      element.style.removeProperty("--tilt-y");
    }

    function clearDrag() {
      if (!dragCandidate) return;
      const { element, swapTarget } = dragCandidate;
      swapTarget?.classList.remove("dashboard-drag-over");
      element.classList.remove("dashboard-dragging", "dashboard-drag-ready");
      element.style.removeProperty("--drag-x");
      element.style.removeProperty("--drag-y");
      document.body.classList.remove("dashboard-reordering");
      dragCandidate = null;
    }

    function onPointerMove(event: PointerEvent) {
      if (reducedMotion.matches || event.pointerType === "touch") return;
      const element = findTarget(event.target);
      if (!element) return;

      if (activeElement && activeElement !== element) clearActive(activeElement);
      activeElement = element;

      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const px = Math.min(100, Math.max(0, (x / rect.width) * 100));
      const py = Math.min(100, Math.max(0, (y / rect.height) * 100));
      const tiltX = ((py - 50) / 50) * -2.2;
      const tiltY = ((px - 50) / 50) * 2.2;

      element.classList.add("motion-target", "motion-active");
      element.style.setProperty("--pointer-x", `${px}%`);
      element.style.setProperty("--pointer-y", `${py}%`);
      element.style.setProperty("--tilt-x", `${tiltX}deg`);
      element.style.setProperty("--tilt-y", `${tiltY}deg`);
    }

    function onPointerOut(event: PointerEvent) {
      const element = findTarget(event.target);
      if (!element) return;
      if (event.relatedTarget instanceof Node && element.contains(event.relatedTarget)) return;
      clearActive(element);
      if (activeElement === element) activeElement = null;
    }

    function onPointerDown(event: PointerEvent) {
      if (event.button !== 0 || event.pointerType === "touch") return;
      const element = findDashboardDragTarget(event.target);
      if (!element) return;
      dragCandidate = {
        element,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        dragging: false,
        swapTarget: null,
      };
      element.classList.add("dashboard-drag-ready");
    }

    function onDashboardDrag(event: PointerEvent) {
      if (!dragCandidate || dragCandidate.pointerId !== event.pointerId) return;
      const dx = event.clientX - dragCandidate.startX;
      const dy = event.clientY - dragCandidate.startY;
      if (!dragCandidate.dragging && Math.hypot(dx, dy) < 4) return;
      dragCandidate.dragging = true;
      suppressNextClick = true;
      const dragX = dx;
      const dragY = dy;
      document.body.classList.add("dashboard-reordering");
      dragCandidate.element.classList.add("dashboard-dragging", "motion-target");
      dragCandidate.element.style.setProperty("--drag-x", `${dragX}px`);
      dragCandidate.element.style.setProperty("--drag-y", `${dragY}px`);
      setSwapTarget(findSwapTargetAtPoint(event.clientX, event.clientY));
      event.preventDefault();
    }

    function onPointerUp(event: PointerEvent) {
      if (!dragCandidate || dragCandidate.pointerId !== event.pointerId) return;
      const wasDragging = dragCandidate.dragging;
      const dragged = dragCandidate.element;
      const swapTarget = dragCandidate.swapTarget;
      clearDrag();
      if (wasDragging && swapTarget) {
        swapElements(dragged, swapTarget);
        dragged.classList.add("dashboard-replaced");
        swapTarget.classList.add("dashboard-replaced");
        window.setTimeout(() => {
          dragged.classList.remove("dashboard-replaced");
          swapTarget.classList.remove("dashboard-replaced");
        }, 460);
      }
      if (wasDragging) {
        window.setTimeout(() => {
          suppressNextClick = false;
        }, 80);
      }
    }

    function onClick(event: MouseEvent) {
      if (reducedMotion.matches) return;
      if (suppressNextClick) {
        event.preventDefault();
        event.stopPropagation();
        suppressNextClick = false;
        return;
      }
      const element = findClickTarget(event.target);
      if (!element || isDisabled(element)) return;

      element.classList.remove("motion-clicked");
      void element.offsetWidth;
      element.classList.add("motion-clicked");
      window.setTimeout(() => element.classList.remove("motion-clicked"), 360);

      if (isFormControl(element)) return;

      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const ripple = document.createElement("span");
      const size = Math.max(rect.width, rect.height) * 1.2;
      ripple.className = "motion-ripple";
      ripple.style.width = `${size}px`;
      ripple.style.height = `${size}px`;
      ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
      ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
      element.classList.add("motion-target");
      element.appendChild(ripple);
      window.setTimeout(() => ripple.remove(), 620);
    }

    document.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointermove", onDashboardDrag, { passive: false });
    document.addEventListener("pointerdown", onPointerDown, { passive: true });
    document.addEventListener("pointerup", onPointerUp, { passive: true });
    document.addEventListener("pointercancel", onPointerUp, { passive: true });
    document.addEventListener("pointerout", onPointerOut, { passive: true });
    document.addEventListener("click", onClick);

    return () => {
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointermove", onDashboardDrag);
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("pointerup", onPointerUp);
      document.removeEventListener("pointercancel", onPointerUp);
      document.removeEventListener("pointerout", onPointerOut);
      document.removeEventListener("click", onClick);
      clearActive(activeElement);
      clearDrag();
    };
  }, []);

  return null;
}
