'use client';

import React, { useEffect, useRef } from 'react';

interface TileData {
  el: HTMLDivElement;
  col: number;
  row: number;
  centerX: number;
  centerY: number;
  offTimeoutId: number | null;
}

export const TileMosaic: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tilesRef = useRef<TileData[]>([]);
  const timeoutsRef = useRef<Set<number>>(new Set());
  const rafRef = useRef<number | null>(null);
  const shuffleIntervalRef = useRef<number | null>(null);
  const lastPointerTimeRef = useRef<number>(0);
  const pointerPosRef = useRef<{ x: number; y: number } | null>(null);
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    startTimeRef.current = performance.now();
    const container = containerRef.current;
    if (!container) return;

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const clearAllTimeouts = () => {
      timeoutsRef.current.forEach((id) => clearTimeout(id));
      timeoutsRef.current.clear();
      tilesRef.current.forEach((tile) => {
        if (tile.offTimeoutId !== null) {
          clearTimeout(tile.offTimeoutId);
          tile.offTimeoutId = null;
        }
      });
      if (shuffleIntervalRef.current) {
        clearInterval(shuffleIntervalRef.current);
        shuffleIntervalRef.current = null;
      }
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    const buildGrid = () => {
      clearAllTimeouts();
      container.innerHTML = '';
      tilesRef.current = [];

      const rect = container.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      if (width === 0 || height === 0) return;

      const tileSize = width >= 768 ? 80 : 56;
      const cols = Math.ceil(width / tileSize);
      const rows = Math.ceil(height / tileSize);

      container.style.display = 'grid';
      container.style.gridTemplateColumns = `repeat(${cols}, ${tileSize}px)`;
      container.style.gridTemplateRows = `repeat(${rows}, ${tileSize}px)`;
      container.style.width = '100%';
      container.style.height = '100%';

      const fragment = document.createDocumentFragment();
      const newTiles: TileData[] = [];

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const tileEl = document.createElement('div');
          tileEl.className = 'tile-wrapper relative overflow-hidden';
          tileEl.style.width = `${tileSize}px`;
          tileEl.style.height = `${tileSize}px`;

          const innerEl = document.createElement('div');
          innerEl.className = 'tile-inner';

          const frontEl = document.createElement('div');
          frontEl.className = 'tile-front';

          const backEl = document.createElement('div');
          backEl.className = 'tile-back';

          innerEl.appendChild(frontEl);
          innerEl.appendChild(backEl);
          tileEl.appendChild(innerEl);
          fragment.appendChild(tileEl);

          const isSelected = Math.random() < 0.12;

          const tileData: TileData = {
            el: tileEl,
            col: c,
            row: r,
            centerX: c * tileSize + tileSize / 2,
            centerY: r * tileSize + tileSize / 2,
            offTimeoutId: null,
          };

          if (isSelected) {
            if (prefersReducedMotion) {
              tileEl.classList.add('is-on');
            } else {
              const delay = (c + r) * 35;
              const tid = window.setTimeout(() => {
                tileEl.classList.add('is-on');
                timeoutsRef.current.delete(tid);
              }, delay);
              timeoutsRef.current.add(tid);
            }
          }

          newTiles.push(tileData);
        }
      }

      container.appendChild(fragment);
      tilesRef.current = newTiles;

      if (prefersReducedMotion) return;

      // Ambient shuffle every 4.2 seconds
      shuffleIntervalRef.current = window.setInterval(() => {
        const tiles = tilesRef.current;
        if (!tiles.length) return;
        const count = Math.floor(Math.random() * 2) + 1;
        for (let i = 0; i < count; i++) {
          const randomTile = tiles[Math.floor(Math.random() * tiles.length)];
          if (randomTile && !randomTile.el.classList.contains('is-on')) {
            randomTile.el.classList.add('is-on');
            const tid = window.setTimeout(() => {
              randomTile.el.classList.remove('is-on');
              timeoutsRef.current.delete(tid);
            }, 1400);
            timeoutsRef.current.add(tid);
          }
        }
      }, 4200);

      // Start virtual probe animation loop
      let lastFrameTime = performance.now();
      const loop = (currentTime: number) => {
        const timeSincePointer = currentTime - lastPointerTimeRef.current;

        if (timeSincePointer > 2500) {
          const elapsed = (currentTime - startTimeRef.current) * 0.00045;
          const probeX = width * 0.5 + Math.sin(elapsed) * (width * 0.38);
          const probeY =
            height * 0.5 +
            Math.sin(elapsed * 2) * Math.cos(elapsed) * (height * 0.35);

          const probeRadius = 110;
          for (let i = 0; i < tilesRef.current.length; i++) {
            const tile = tilesRef.current[i];
            const dx = tile.centerX - probeX;
            const dy = tile.centerY - probeY;
            if (dx * dx + dy * dy < probeRadius * probeRadius) {
              triggerTile(tile, 1000);
            }
          }
        }

        rafRef.current = requestAnimationFrame(loop);
      };

      rafRef.current = requestAnimationFrame(loop);
    };

    const triggerTile = (tile: TileData, duration: number = 1200) => {
      if (tile.offTimeoutId !== null) {
        clearTimeout(tile.offTimeoutId);
      } else {
        tile.el.classList.add('is-on');
      }

      tile.offTimeoutId = window.setTimeout(() => {
        tile.el.classList.remove('is-on');
        tile.offTimeoutId = null;
      }, duration);
    };

    const handlePointerMove = (e: PointerEvent) => {
      lastPointerTimeRef.current = performance.now();
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      pointerPosRef.current = { x, y };

      const radius = 140;
      const radiusSq = radius * radius;
      const tiles = tilesRef.current;

      for (let i = 0; i < tiles.length; i++) {
        const tile = tiles[i];
        const dx = tile.centerX - x;
        const dy = tile.centerY - y;
        if (dx * dx + dy * dy < radiusSq) {
          triggerTile(tile, 1200);
        }
      }
    };

    buildGrid();

    window.addEventListener('pointermove', handlePointerMove, { passive: true });

    let resizeTimeout: number;
    const handleResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = window.setTimeout(buildGrid, 200);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      clearAllTimeouts();
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 z-0 overflow-hidden"
      aria-hidden="true"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
      }}
    />
  );
};
