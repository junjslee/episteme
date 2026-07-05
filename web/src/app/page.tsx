import { Header } from "@/components/site/Header";
import { Hero } from "@/components/site/Hero";
import { Sectioned } from "@/components/ui/Sectioned";
import { EngineFlowLoader } from "@/components/site/EngineFlowLoader";
import { SurfaceWalk } from "@/components/site/SurfaceWalk";
import { ThreeLayers } from "@/components/site/ThreeLayers";
import { ProofSection } from "@/components/site/ProofSection";
import { FrameworkExplainer } from "@/components/site/FrameworkExplainer";
import { InstallSection } from "@/components/site/InstallSection";
import { Footer } from "@/components/site/Footer";

// Six-beat one-scroll arc: WHAT IS THIS → HOW DOES IT WORK → FEEL IT →
// WHERE IT RUNS → IS IT REAL → HOW DO I GET IT. Empty legacy anchors keep
// old deep links (/#framework, /#surface, /#protocols) scrolling to the
// nearest successor.

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <span id="framework" aria-hidden />
        <Sectioned
          id="how-it-works"
          index="01"
          label="how it works"
          kicker="decision → interrogation → verdict → chain"
        >
          <EngineFlowLoader />
        </Sectioned>
        <span id="surface" aria-hidden />
        <SurfaceWalk />
        <ThreeLayers />
        <ProofSection />
        <FrameworkExplainer />
        <span id="protocols" aria-hidden />
        <InstallSection />
      </main>
      <Footer />
    </>
  );
}
