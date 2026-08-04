import AIScene from '../components/AI/AIScene';
import { useFridayStore } from '../store/useFridayStore';

export default function Home() {
  const assistantState = useFridayStore((s) => s.assistantState);

  return (
    <main className="absolute inset-0 bg-[#050505]">
      <div className="absolute inset-0">
        <AIScene state={assistantState} />
      </div>
    </main>
  );
}
