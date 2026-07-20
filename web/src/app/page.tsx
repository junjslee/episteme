import { Header } from "@/components/site/Header";
import { Hero } from "@/components/site/Hero";
import { MomentItWorks } from "@/components/site/MomentItWorks";
import { HowItWorks } from "@/components/site/HowItWorks";
import { WayToThink } from "@/components/site/WayToThink";
import { Install } from "@/components/site/Install";
import { Footer } from "@/components/site/Footer";

/**
 * Landing — "The Gate & the Lattice" (Event 164).
 *
 * Arc: SEE IT (the 3D gate holding an action) → BELIEVE IT (a real block
 * message and its repair) → UNDERSTAND IT (declare / gate / learn) → WHY IT
 * MATTERS (the practice) → GET IT (install).
 *
 * Empty legacy anchors keep old deep links (/#framework, /#surface,
 * /#protocols, /#proof) scrolling to their nearest successor section.
 */
export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <span id="framework" aria-hidden />
        <span id="proof" aria-hidden />
        <MomentItWorks />
        <span id="surface" aria-hidden />
        <HowItWorks />
        <span id="protocols" aria-hidden />
        <WayToThink />
        <Install />
      </main>
      <Footer />
    </>
  );
}
