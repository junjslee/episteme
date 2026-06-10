import { Header } from "@/components/site/Header";
import { Hero } from "@/components/site/Hero";
import { HowItWorks } from "@/components/site/HowItWorks";
import { ThreeLayers } from "@/components/site/ThreeLayers";
import { ProofSection } from "@/components/site/ProofSection";
import { FrameworkExplainer } from "@/components/site/FrameworkExplainer";
import { InstallSection } from "@/components/site/InstallSection";
import { Footer } from "@/components/site/Footer";

// Five-beat one-scroll arc: WHAT IS THIS → HOW DOES IT WORK → WHERE IT RUNS
// → IS IT REAL → HOW DO I GET IT. Empty legacy anchors keep old deep links
// (/#framework, /#surface, /#protocols) scrolling to the nearest successor.

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <span id="framework" aria-hidden />
        <HowItWorks />
        <ThreeLayers />
        <span id="surface" aria-hidden />
        <ProofSection />
        <FrameworkExplainer />
        <span id="protocols" aria-hidden />
        <InstallSection />
      </main>
      <Footer />
    </>
  );
}
