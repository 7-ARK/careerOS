/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Header } from './components/Header';
import { Hero } from './components/Hero';
import { AnalyzeJob } from './components/AnalyzeJob';
import { FolderJourney } from './components/FolderJourney';
import { Features } from './components/Features';
import { CTA } from './components/CTA';
import { Footer } from './components/Footer';

export default function App() {
  return (
    <div className="relative min-h-screen bg-background text-foreground font-sans antialiased selection:bg-primary/20 selection:text-foreground">
      <Header />
      <main className="relative" id="main-content-layout">
        <Hero />
        <AnalyzeJob />
        <FolderJourney />
        <Features />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
