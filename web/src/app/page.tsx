import { Header } from "@/components/site/Header";
import { Hero } from "@/components/site/Hero";
import { ReasoningSurfaceShowcase } from "@/components/site/ReasoningSurfaceShowcase";
import { PillarsGrid } from "@/components/site/PillarsGrid";
import { LiveExhibit } from "@/components/site/LiveExhibit";
import { FrameworkExplainer } from "@/components/site/FrameworkExplainer";
import { ProtocolsSection } from "@/components/site/ProtocolsSection";
import { CodeSample } from "@/components/site/CodeSample";
import { SymbiosisTimeline } from "@/components/site/SymbiosisTimeline";
import { CTASection } from "@/components/site/CTASection";
import { Footer } from "@/components/site/Footer";

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <ReasoningSurfaceShowcase />
        <PillarsGrid />
        <LiveExhibit />
        <FrameworkExplainer />
        <ProtocolsSection />
        <CodeSample />
        <SymbiosisTimeline />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
