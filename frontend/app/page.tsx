import React from 'react';
import { Navbar } from './components/landing/Navbar';
import { Hero } from './components/landing/Hero';
import { Process } from './components/landing/Process';
import { Work } from './components/landing/Work';
import { Studio } from './components/landing/Studio';
import { Contact } from './components/landing/Contact';

export default function LandingPage() {
  return (
    <div className="landing-container">
      <Navbar />
      <main>
        <Hero />
        <Process />
        <Work />
        <Studio />
        <Contact />
      </main>
    </div>
  );
}
