import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  AreaChart, Area, ReferenceLine, Cell, LabelList, Label, ReferenceArea, Legend,
  BarChart, Bar, LineChart, Line
} from 'recharts';
import { 
  Wifi, WifiOff, Trash2, MapPin, 
  AlertTriangle, CheckCircle, RefreshCw, LayoutDashboard, Database as TableIcon,
  Sun, Moon, Volume2, VolumeX, Waves, ShieldCheck, ShieldAlert,
  Search, Calendar, FilterX, ChevronLeft, ChevronRight, Activity, FileSpreadsheet,
  Droplets, Info, Lock
} from 'lucide-react';

const CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQd963Q6VuLwBc2ZY5Ll_37AbrH0dbemKBEH4SNWtR1jHkWYARbf9jPvGuBzjtwT8kbJZUEk5TPWZBh/pub?output=csv";
const MBSP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/7/78/Seberang_Perai_City_Council_%28MBSP_-_Majlis_Bandaraya_Seberang_Perai%29_Logo.png";

const App = () => {
  const [isInitializing, setIsInitializing] = useState(true);
  const [initProgress, setInitProgress] = useState(0);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentPage, setCurrentPage] = useState('overview');
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const [theme, setTheme] = useState('light');
  const [selectedBarDate, setSelectedBarDate] = useState('all');
  
  const [filterStartDate, setFilterStartDate] = useState('');
  const [filterEndDate, setFilterEndDate] = useState('');
  const [filterTrashStatus, setFilterTrashStatus] = useState('ALL');
  const [filterHydroLevel, setFilterHydroLevel] = useState('ALL');

  const [isAudioEnabled, setIsAudioEnabled] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState(
    "https://hook.eu1.make.com/ctn37dg9urwlnn3y5c8hqie9ddwbq1g1"
  );

  const [lastAlertTime, setLastAlertTime] = useState(0);
  const audioContext = useRef(null);

  // MBSP Initialization Sequence
  useEffect(() => {
    const timer = setInterval(() => {
      setInitProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          setTimeout(() => setIsInitializing(false), 800);
          return 100;
        }
        return prev + 2;
      });
    }, 40);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (theme === 'dark') document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [theme]);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // --- AUDIO ALARM LOGIC ---
  const playAlarm = () => {
    if (!isAudioEnabled) return;
    try {
      if (!audioContext.current) {
        audioContext.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      // Resume context if it was suspended (browser policy)
      if (audioContext.current.state === 'suspended') {
        audioContext.current.resume();
      }
      
      const osc = audioContext.current.createOscillator();
      const gain = audioContext.current.createGain();
      
      osc.type = 'sawtooth';
      // Alarm frequency pattern
      osc.frequency.setValueAtTime(880, audioContext.current.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, audioContext.current.currentTime + 0.5);
      
      gain.gain.setValueAtTime(0.1, audioContext.current.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioContext.current.currentTime + 0.5);
      
      osc.connect(gain);
      gain.connect(audioContext.current.destination);
      
      osc.start();
      osc.stop(audioContext.current.currentTime + 0.5);
    } catch (e) {
      console.error("Audio error", e);
    }
  };

  // --- MAKE.COM WEBHOOK INTEGRATION ---
  const triggerExternalAlert = async (type, payload) => {
    const now = Date.now();
    // 5-minute cooldown between alerts to prevent spamming the webhook
    if (webhookUrl && (now - lastAlertTime > 300000)) {
      try {
        await fetch(webhookUrl, {
          method: 'POST',
          mode: 'no-cors',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: type, // e.g. "TRASH_DETECTED" or "HIGH_WATER_LEVEL"
            ...payload,
            timestamp: new Date().toISOString(),
            location: "Taman Sri Rambai Node #001"
          })
        });
        setLastAlertTime(now);
      } catch (err) {
        console.error("Webhook failed", err);
      }
    }
  };

  const fetchData = async (retries = 5, delay = 1000) => {
    setIsRefreshing(true);
    try {
      const cacheBuster = `&t=${new Date().getTime()}`;
      const response = await fetch(CSV_URL + cacheBuster);
      const text = await response.text();
      const rows = text.split('\n').slice(1);
      
      const parsedData = rows.map(row => {
        const cols = row.split(',');
        const rawTof = parseFloat(cols[2]) || 0;
        const isTrashDetected = rawTof >= 1120;
        
        let rawLevel = cols[3]?.trim().toUpperCase() || "LOW";
        let displayLevel = "LOW";
        if (rawLevel.includes("HIGH") || rawLevel === "3") displayLevel = "HIGH";
        else if (rawLevel.includes("NORMAL") || rawLevel === "2") displayLevel = "NORMAL";
        else displayLevel = "LOW";

        let rawStatus = cols[4]?.trim().toUpperCase() || "NORMAL";
        let displayStatus = "NORMAL";
        if (rawStatus.includes("ALERT") || rawStatus === "3") displayStatus = "ALERT";
        else if (rawStatus.includes("WARNING") || rawStatus === "2") displayStatus = "WARNING";
        else displayStatus = "NORMAL";

        return {
          date: cols[0]?.trim(),
          wifi: cols[1]?.trim() || "N/A",
          tof: rawTof,
          trashStatus: isTrashDetected ? "DETECTED" : "NOT DETECTED",
          level: displayLevel,
          status: displayStatus
        };
      }).filter(d => d.date && !d.date.includes("DATE") && !d.date.includes("THE"));
      
      const latestPoint = parsedData[parsedData.length - 1];
      
      // CHECK ALERT CONDITIONS
      if (latestPoint) {
        // Trigger 1: Trash Detected (ToF >= 1120)
        if (latestPoint.tof >= 1120) {
          playAlarm();
          triggerExternalAlert("TRASH_DETECTED_ALARM", {
            tof_value: latestPoint.tof,
            hydro_level: latestPoint.level
          });
        }
        
        // Trigger 2: High Hydro Level detected in Spreadsheet
        if (latestPoint.level === "HIGH") {
          // Additional alarm for flood risk
          playAlarm(); 
          triggerExternalAlert("HIGH_WATER_ALERT", {
            current_level: latestPoint.level,
            trash_status: latestPoint.trashStatus
          });
        }
      }

      setData(parsedData);
      setLoading(false);
      setIsRefreshing(false);
    } catch (error) {
      if (retries > 0) setTimeout(() => fetchData(retries - 1, delay * 2), delay);
      else { setLoading(false); setIsRefreshing(false); }
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [isAudioEnabled, webhookUrl]);

  const latest = data[data.length - 1] || {};
  const isWifiConnected = latest.wifi?.toUpperCase().includes('CONNECTED');
  
  const filteredDatabase = useMemo(() => {
    return data.filter(item => {
      const dateStr = item.date.split(' ')[0];
      const [d, m, y] = dateStr.split('-');
      const itemDate = `${y}-${m}-${d}`;

      const matchesStart = filterStartDate ? itemDate >= filterStartDate : true;
      const matchesEnd = filterEndDate ? itemDate <= filterEndDate : true;
      const matchesTrash = filterTrashStatus === 'ALL' ? true : item.trashStatus === filterTrashStatus;
      const matchesLevel = filterHydroLevel === 'ALL' ? true : item.level === filterHydroLevel;

      return matchesStart && matchesEnd && matchesTrash && matchesLevel;
    }).reverse();
  }, [data, filterStartDate, filterEndDate, filterTrashStatus, filterHydroLevel]);

  const chartData = useMemo(() => {
    if (!data.length) return { lineData: [], barData: [], totalDetectionsForSelected: 0, depthHistory: [] };
    
    const levelMap = { 'LOW': 1, 'NORMAL': 2, 'HIGH': 3 };

    const lineData = data.slice(-50).map(item => ({
      time: item.date,
      val: levelMap[item.level] || 1,
      label: item.level
    }));

    const depthHistory = data.slice(-100).map(item => ({
      timestamp: item.date,
      depth: item.tof,
      risk: item.tof >= 1120 ? 'HIGH' : item.tof >= 800 ? 'WARNING' : 'STABLE'
    }));

    if (selectedBarDate !== 'all') {
      const filtered = data.filter(d => d.date.startsWith(selectedBarDate));
      let totalDetections = 0;
      
      const barData = filtered.map((item) => {
        let timePart = "00:00";
        const isDetected = item.tof >= 1120;
        if (isDetected) totalDetections++;
        
        try {
          const parts = item.date.split(/[ T]/);
          if (parts.length > 1) {
            timePart = parts[1].substring(0, 5); 
          }
        } catch (e) {}

        return {
          date: `${timePart}`,
          count: isDetected ? 1 : 0,
          label: isDetected ? 'DETECTED' : 'CLEAR'
        };
      });

      return { lineData, barData, totalDetectionsForSelected: totalDetections, depthHistory };
    } else {
      const dailyCounts = data.reduce((acc, curr) => {
        const dayRaw = curr.date.split(/[ T]/)[0]; 
        if (dayRaw && /\d/.test(dayRaw)) {
          if (!acc[dayRaw]) acc[dayRaw] = 0;
          if (curr.tof >= 1120) { 
            acc[dayRaw] += 1;
          }
        }
        return acc;
      }, {});

      const barData = Object.entries(dailyCounts)
        .map(([rawDate, count]) => {
          let displayDate = rawDate;
          try {
            const d = new Date(rawDate);
            if (!isNaN(d.getTime())) {
              const day = String(d.getDate()).padStart(2, '0');
              const month = String(d.getMonth() + 1).padStart(2, '0');
              const year = String(d.getFullYear()).slice(-2);
              displayDate = `${day}/${month}/${year}`;
            }
          } catch (e) {}
          
          return { 
            date: displayDate,
            fullDate: rawDate,
            count: count > 0 ? 1 : 0,
            actualCount: count,
            label: count > 0 ? 'DETECTED' : 'CLEAR'
          };
        })
        .sort((a, b) => new Date(a.fullDate) - new Date(b.fullDate))
        .slice(-10);

      const totalAcrossAll = Object.values(dailyCounts).reduce((a, b) => a + b, 0);

      return { lineData, barData, totalDetectionsForSelected: totalAcrossAll, depthHistory };
    }
  }, [data, selectedBarDate]);

  const handleExportCSV = () => {
    if (filteredDatabase.length === 0) return;
    const headers = ["Timestamp", "WiFi Status", "ToF Reading (us)", "Trash Status", "Hydro Level", "Operational Status"];
    const csvRows = filteredDatabase.map(row => [
      `"${row.date}"`,
      `"${row.wifi}"`,
      row.tof,
      `"${row.trashStatus}"`,
      `"${row.level}"`,
      `"${row.status}"`
    ]);
    const csvContent = [headers, ...csvRows].map(e => e.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    link.setAttribute("href", url);
    link.setAttribute("download", `IoT_TrashRake_Filtered_${timestamp}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (isInitializing) {
    return (
      <div className="fixed inset-0 z-[100] bg-slate-900 flex items-center justify-center p-6 text-center">
  
  {/* Background gradient */}
  <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-900 to-slate-950"></div>

  {/* Content */}
  <div className="relative z-10 animate-in zoom-in-95 duration-700 flex flex-col items-center">
    
    {/* Logo container */}
    <div className="relative w-fit flex items-center justify-center mb-8">
      
      {/* Glow */}
      <div className="absolute inset-0 bg-white/20 blur-3xl rounded-full scale-125"></div>

      {/* Logo */}
      <img 
        src={MBSP_LOGO} 
        alt="MBSP Logo"
        className="relative z-10 w-48 md:w-64 h-auto animate-pulse drop-shadow-[0_0_20px_rgba(255,255,255,0.4)]"
        onError={(e) => (e.target.style.display = 'none')}
   



            />
          </div>
          
          <div className="space-y-6">
            <div className="space-y-2">
              <h2 className="text-white font-black text-2xl md:text-3xl tracking-tighter uppercase italic">
                Majlis Bandaraya Seberang Perai
              </h2>
              <div className="flex items-center justify-center gap-2">
                <div className="h-px w-8 bg-blue-500"></div>
                <p className="text-blue-400 font-black text-xs uppercase tracking-[0.4em]">
                  SMART DRAINAGE INITIATIVE
                </p>
                <div className="h-px w-8 bg-blue-500"></div>
              </div>
            </div>

            <div className="w-64 h-1 bg-white/10 rounded-full overflow-hidden mx-auto border border-white/5">
              <div 
                className="h-full bg-gradient-to-r from-blue-600 via-cyan-400 to-blue-600 transition-all duration-300 ease-out"
                style={{ width: `${initProgress}%` }}
              ></div>
            </div>
            
            <div className="flex flex-col gap-1">
               <p className="text-slate-400 font-mono text-[9px] uppercase tracking-widest animate-pulse">
                {initProgress < 30 ? "Initializing Cloud Telemetry..." : 
                 initProgress < 60 ? "Establishing Secure Sensor Link..." :
                 initProgress < 90 ? "Mapping Sri Rambai Geofence..." : "Ready to Launch Dashboard"}
               </p>
               <div className="flex items-center justify-center gap-1.5">
                  <Lock size={10} className="text-emerald-500" />
                  <p className="text-emerald-500/80 font-bold text-[8px] uppercase tracking-widest">Secure Handshake: OK</p>
               </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const KPICard = ({ title, value, icon: Icon, gradient, subValue, delayClass }) => (
    <div className={`relative group overflow-hidden rounded-2xl p-[1px] transition-all duration-500 hover:scale-[1.03] hover:-translate-y-1 shadow-lg dark:shadow-none animate-in slide-in-from-bottom-8 fade-in ${delayClass}`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-20 group-hover:opacity-100 blur-xl transition-opacity duration-700`}></div>
      <div className="relative bg-white dark:bg-slate-900/90 backdrop-blur-xl p-5 rounded-2xl h-full border border-slate-200 dark:border-white/5 overflow-hidden">
        <div className={`absolute -right-4 -top-4 w-24 h-24 bg-gradient-to-br ${gradient} opacity-5 rounded-full group-hover:scale-150 transition-transform duration-1000`}></div>
        <div className="flex justify-between items-start mb-4 relative z-10">
          <div className={`p-3 rounded-xl bg-gradient-to-br ${gradient} shadow-lg shadow-black/10 transform group-hover:rotate-12 transition-transform duration-300`}>
            <Icon className="text-white" size={24} />
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">Node_Active</span>
            <div className={`w-2 h-2 rounded-full bg-emerald-500 animate-pulse mt-1 shadow-[0_0_8px_rgba(16,185,129,0.8)]`}></div>
          </div>
        </div>
        <div className="relative z-10">
          <h3 className="text-slate-700 dark:text-slate-300 font-bold text-[11px] uppercase tracking-wide leading-tight min-h-[32px] mb-1">{title}</h3>
          <p className="text-2xl font-black text-slate-900 dark:text-white uppercase tracking-tighter leading-tight group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r transition-all duration-300 ${gradient.replace('from-', 'group-hover:from-').replace('to-', 'group-hover:to-')}">
            {value}
          </p>
          <div className="flex items-center gap-2 mt-2">
             <div className="h-1 w-12 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${gradient} animate-progress-fast`}></div>
             </div>
             <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono italic font-bold">{subValue}</p>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 p-4 md:p-8 font-sans transition-colors duration-500 relative overflow-hidden">
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none opacity-30 dark:opacity-20 z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-500/20 blur-[120px] animate-blob"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/20 blur-[120px] animate-blob animation-delay-2000"></div>
      </div>

      <header className="relative z-10 mb-8 flex flex-col md:flex-row md:items-center justify-between gap-6 animate-in fade-in slide-in-from-top-6 duration-1000 ease-out">
        <div className="group flex items-center gap-5">
          <img src={MBSP_LOGO} alt="MBSP" className="w-12 h-auto opacity-80 group-hover:opacity-100 transition-opacity" />
          <div>
            <h1 className="text-2xl md:text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-700 via-blue-700 to-purple-700 dark:from-cyan-400 dark:via-blue-500 dark:to-purple-500 tracking-tighter transition-all duration-500 group-hover:tracking-normal">
              IOT TRASH RAKE MONITORING SYSTEM
            </h1>
            <div className="flex items-center gap-2 mt-2">
              <div className="flex gap-1">
                 <span className="w-2 h-1 bg-cyan-500 rounded-full animate-bounce"></span>
                 <span className="w-2 h-1 bg-blue-500 rounded-full animate-bounce delay-150"></span>
                 <span className="w-2 h-1 bg-purple-500 rounded-full animate-bounce delay-300"></span>
              </div>
              <p className="text-slate-700 dark:text-slate-300 font-bold uppercase text-[10px] tracking-[0.2em]">
                Drainage Telemetry Dashboard • Seberang Perai City Council
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border border-slate-200 dark:border-white/10 p-4 rounded-2xl flex items-center gap-6 shadow-2xl hover:border-blue-500/50 transition-colors duration-500">
          <button 
            onClick={() => setIsAudioEnabled(!isAudioEnabled)}
            className={`group relative p-3 rounded-xl transition-all duration-300 ${isAudioEnabled ? 'bg-rose-500 text-white shadow-[0_0_15px_rgba(244,63,94,0.5)]' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'}`}
          >
            {isAudioEnabled ? <Volume2 size={22} className="animate-wiggle" /> : <VolumeX size={22} />}
            {isAudioEnabled && <span className="absolute -top-1 -right-1 w-3 h-3 bg-white rounded-full animate-ping"></span>}
          </button>
          
          <div className="h-10 w-[1px] bg-slate-200 dark:bg-white/10 hidden sm:block"></div>
          
          <div className="text-right">
            <p className="text-[10px] text-slate-600 dark:text-slate-400 uppercase font-black tracking-widest">System Engine</p>
            <p className="text-xl font-mono font-black text-cyan-700 dark:text-cyan-400 tabular-nums tracking-tight">
                {currentTime.toLocaleTimeString([], { hour12: false })}
            </p>
          </div>
          
          <div className="flex gap-2">
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors shadow-sm">
              {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <button onClick={() => fetchData()} className={`p-3 rounded-xl bg-blue-600/10 text-blue-600 hover:bg-blue-600 hover:text-white transition-all duration-500 ${isRefreshing ? 'animate-spin' : ''}`}>
              <RefreshCw size={20} />
            </button>
          </div>
        </div>
      </header>

      <nav className="relative z-10 flex gap-3 mb-10 animate-in fade-in slide-in-from-left-6 duration-1000 delay-200">
        {[
          { id: 'overview', icon: LayoutDashboard, label: 'Control Center' },
          { id: 'analytics', icon: TableIcon, label: 'Historical Logs' }
        ].map(tab => (
          <button 
            key={tab.id}
            onClick={() => setCurrentPage(tab.id)} 
            className={`group relative flex items-center gap-3 px-8 py-3 rounded-2xl font-black text-xs uppercase tracking-widest transition-all duration-500 overflow-hidden ${
              currentPage === tab.id 
                ? 'bg-blue-700 text-white shadow-lg' 
                : 'bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-transparent hover:border-blue-500 dark:hover:border-white/10'
            }`}
          >
            <tab.icon size={18} className={`${currentPage === tab.id ? 'animate-pulse' : 'group-hover:scale-110 transition-transform'}`} />
            {tab.label}
          </button>
        ))}
      </nav>

      {currentPage === 'overview' ? (
        <div className="relative z-10 space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <KPICard title="System Connection Status" value={isWifiConnected ? "Link Active" : "Link Down"} icon={isWifiConnected ? Wifi : WifiOff} gradient={isWifiConnected ? "from-emerald-600 to-teal-400" : "from-rose-600 to-pink-500"} subValue={latest.wifi || "No Ping"} delayClass="delay-[100ms]" />
            <KPICard title="Trash Detection Scan" value={latest.trashStatus || "SCANNING..."} icon={latest.tof >= 1120 ? Search : Trash2} gradient={latest.tof >= 1120 ? "from-rose-600 to-red-500" : "from-emerald-600 to-teal-500"} subValue={`ToF Reading: ${latest.tof || 0} µs`} delayClass="delay-[200ms]" />
            <KPICard title="Current Flow Dynamics" value={latest.level || "READING..."} icon={Waves} gradient={latest.level === "HIGH" ? "from-rose-600 to-red-500" : latest.level === "NORMAL" ? "from-emerald-600 to-teal-500" : "from-cyan-500 to-blue-500"} subValue="Hydrostatic Pressure" delayClass="delay-[300ms]" />
            <KPICard title="Operational Integrity" value={latest.status || "IDLE"} icon={latest.status === "ALERT" ? ShieldAlert : latest.status === "WARNING" ? AlertTriangle : ShieldCheck} gradient={latest.status === "ALERT" ? "from-rose-600 to-red-500" : latest.status === "WARNING" ? "from-amber-500 to-orange-400" : "from-emerald-600 to-teal-500"} subValue="Core Health Diagnostic" delayClass="delay-[400ms]" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="group bg-white dark:bg-slate-900/80 backdrop-blur-xl border border-slate-200 dark:border-white/5 rounded-3xl p-8 shadow-2xl animate-in slide-in-from-bottom-12 duration-1000 delay-500">
              <div className="flex justify-between items-start mb-8">
                <div>
                  <h3 className="text-xl font-black flex items-center gap-3 text-slate-900 dark:text-white uppercase tracking-tighter">
                    <div className="w-1.5 h-8 bg-blue-600 rounded-full animate-pulse shadow-[0_0_10px_rgba(37,99,235,0.5)]"></div>
                     Drainage Water Level Trend
                  </h3>
                  <p className="text-[10px] text-slate-600 dark:text-slate-400 uppercase font-bold tracking-widest mt-1">Real-Time Telemetry Graph</p>
                </div>
              </div>
              <div className="h-[360px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData.lineData} margin={{ top: 20, right: 30, left: 30, bottom: 40 }}>
                    <defs>
                      <linearGradient id="levelGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2563eb" stopOpacity={0.6}/>
                        <stop offset="95%" stopColor="#2563eb" stopOpacity={0.05}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#1e293b' : '#cbd5e1'} vertical={false} opacity={0.4} />
                    <XAxis 
                      dataKey="time" 
                      fontSize={9} 
                      stroke={theme === 'dark' ? '#94a3b8' : '#475569'} 
                      axisLine={false} 
                      tickLine={false} 
                      minTickGap={40}
                      tickFormatter={(t) => t.includes(':') ? t.split(' ')[1] : t}
                    >
                      <Label value="Monitoring Date" offset={-25} position="insideBottom" style={{ fill: theme === 'dark' ? '#94a3b8' : '#334155', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase' }} />
                    </XAxis>
                    <YAxis 
                      domain={[0.5, 3.5]} 
                      ticks={[1, 2, 3]} 
                      tickFormatter={(val) => val === 1 ? 'LOW' : val === 2 ? 'NORMAL' : val === 3 ? 'HIGH' : ''} 
                      stroke={theme === 'dark' ? '#94a3b8' : '#475569'} 
                      fontSize={10} 
                      fontWeight="bold"
                      axisLine={false} 
                      tickLine={false} 
                    >
                      <Label value="Water Level Category" angle={-90} position="insideLeft" offset={3} style={{ fill: theme === 'dark' ? '#94a3b8' : '#334155', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase', textAnchor: 'middle' }} />
                    </YAxis>
                    <Tooltip contentStyle={{ backgroundColor: theme === 'dark' ? '#0f172a' : '#fff', borderRadius: '8px', border: theme === 'dark' ? '1px solid #334155' : '1px solid #e2e8f0', color: theme === 'dark' ? '#fff' : '#000' }} />
                    <Legend 
                      verticalAlign="top" 
                      align="right" 
                      iconType="circle"
                      wrapperStyle={{ paddingBottom: '20px', fontSize: '9px', fontWeight: 'bold', textTransform: 'uppercase' }}
                      payload={[
                        { value: 'Low Water Level', type: 'circle', id: 'ID01', color: '#3b82f6' },
                        { value: 'Safe Operating Range', type: 'circle', id: 'ID02', color: '#10b981' },
                        { value: 'Flood Risk Threshold', type: 'circle', id: 'ID03', color: '#ef4444' }
                      ]}
                    />
                    <Area type="stepAfter" dataKey="val" stroke="#2563eb" strokeWidth={3} fill="url(#levelGradient)" animationDuration={1000} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden group">
              <div className="mb-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 relative z-10">
                <div>
                  <h3 className="text-xl font-black flex items-center gap-2 text-slate-900 dark:text-white uppercase tracking-tight">
                    <span className="w-2 h-6 bg-rose-500 rounded-full"></span>
                    Daily Trash Detection Events
                  </h3>
                  <p className="text-[10px] text-slate-600 dark:text-slate-400 uppercase font-bold tracking-widest mt-1">
                    {selectedBarDate === 'all' ? 'Aggregate Cleaning Requests' : `Hourly Analysis Log`}
                  </p>
                </div>
                
                <div className="flex items-center gap-2">
                   <div className="relative group/picker">
                      <input 
                        type="date"
                        value={selectedBarDate === 'all' ? '' : selectedBarDate}
                        onChange={(e) => setSelectedBarDate(e.target.value || 'all')}
                        className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl pl-10 pr-4 py-2 text-[10px] font-black uppercase tracking-widest text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 outline-none transition-all cursor-pointer shadow-sm min-w-[160px]"
                      />
                      <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-blue-600" size={14} />
                   </div>
                   {selectedBarDate !== 'all' && (
                     <button 
                       onClick={() => setSelectedBarDate('all')}
                       className="p-2 rounded-xl bg-rose-500/10 text-rose-600 hover:bg-rose-500 hover:text-white transition-all border border-rose-500/20"
                     >
                       <FilterX size={16} />
                     </button>
                   )}
                </div>
              </div>

              <div className={`mb-4 px-4 py-2 rounded-xl border flex items-center gap-3 transition-colors duration-500 ${
                chartData.totalDetectionsForSelected === 0 
                  ? 'bg-emerald-500/10 border-emerald-500/30' 
                  : 'bg-rose-500/10 border-rose-500/30'
              }`}>
                <div className={`w-2 h-2 rounded-full ${chartData.totalDetectionsForSelected === 0 ? 'bg-emerald-500' : 'bg-rose-500 animate-pulse'}`}></div>
                <p className={`text-[11px] font-black uppercase tracking-[0.1em] ${chartData.totalDetectionsForSelected === 0 ? 'text-emerald-800 dark:text-emerald-400' : 'text-rose-800 dark:text-rose-400'}`}>
                  {selectedBarDate === 'all' ? 'Total Period Detections' : `Detections for ${selectedBarDate}`}: {chartData.totalDetectionsForSelected}
                </p>
              </div>

              <div className="h-[320px] relative">
                {chartData.totalDetectionsForSelected === 0 && (
                  <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
                    <div className="bg-white/80 dark:bg-slate-950/80 backdrop-blur-sm px-6 py-4 rounded-2xl border-2 border-emerald-500/30 flex flex-col items-center gap-2 animate-in zoom-in-95 fade-in duration-700 shadow-xl">
                      <CheckCircle className="text-emerald-500" size={32} />
                      <p className="text-xs font-black text-slate-900 dark:text-white uppercase tracking-tighter text-center max-w-[200px]">
                        No trash detected on selected date <br/>
                        <span className="text-emerald-600 dark:text-emerald-400 font-mono text-[10px] tracking-widest">(Normal Operation)</span>
                      </p>
                    </div>
                  </div>
                )}
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData.barData} margin={{ top: 20, right: 30, left: 30, bottom: 45 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#1e293b' : '#cbd5e1'} vertical={false} opacity={0.3} />
                    <XAxis dataKey="date" fontSize={10} fontWeight="bold" stroke={theme === 'dark' ? '#94a3b8' : '#334155'} axisLine={false} tickLine={false}>
                      <Label value="Monitoring Timeline" offset={-30} position="insideBottom" style={{ fill: theme === 'dark' ? '#94a3b8' : '#334155', fontSize: '10px', fontWeight: 'black', textTransform: 'uppercase', letterSpacing: '0.1em' }} />
                    </XAxis>
                    <YAxis domain={[0, 1]} ticks={[0, 1]} tickFormatter={(val) => val === 1 ? 'DETECTED' : 'CLEAR'} stroke={theme === 'dark' ? '#94a3b8' : '#334155'} fontSize={10} fontWeight="black" axisLine={false} tickLine={false}>
                      <Label value="Trash Detection Status" angle={-90} position="insideLeft" offset={-5} style={{ fill: theme === 'dark' ? '#94a3b8' : '#334155', fontSize: '10px', fontWeight: 'black', textTransform: 'uppercase', textAnchor: 'middle', letterSpacing: '0.05em' }} />
                    </YAxis>
                    <Tooltip cursor={{fill: 'rgba(0, 0, 0, 0.05)'}} contentStyle={{ backgroundColor: theme === 'dark' ? '#0f172a' : '#fff', borderRadius: '12px', border: '1px solid #334155', color: theme === 'dark' ? '#fff' : '#000' }} formatter={(value, name, props) => [props.payload.label, "Status"]} />
                    <Legend verticalAlign="top" align="right" iconType="rect" wrapperStyle={{ paddingBottom: '10px', fontSize: '9px', fontWeight: 'bold', textTransform: 'uppercase' }} payload={[{ value: 'Detected', type: 'rect', color: '#ef4444' }, { value: 'Clear', type: 'rect', color: '#22c55e' }]} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={24}>
                      {chartData.barData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.count > 0 ? '#ef4444' : '#22c55e'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
             <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 overflow-hidden relative group/map shadow-xl">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-black flex items-center gap-2 text-slate-900 dark:text-white uppercase tracking-tight">
                  <MapPin className="text-rose-500" /> Flood Risk Map
                </h3>
                <div className="flex gap-2">
                  <span className="flex items-center gap-1 text-[8px] font-black uppercase text-slate-500">
                    <div className="w-2 h-2 rounded-full bg-rose-500/40"></div> Risk
                  </span>
                  <span className="flex items-center gap-1 text-[8px] font-black uppercase text-slate-500">
                    <div className="w-2 h-2 rounded-full bg-emerald-500/40"></div> Safe
                  </span>
                </div>
              </div>
              <div className="h-[250px] rounded-2xl relative overflow-hidden border border-slate-200 dark:border-slate-800">
                <iframe 
                    width="100%" 
                    height="100%" 
                    src="https://maps.google.com/maps?q=Taman%20Sri%20Rambai,%20Bukit%20Mertajam,%20Pulau%20Pinang&t=h&z=17&ie=UTF8&iwloc=&output=embed" 
                    frameBorder="0"
                    style={{ border: 0, filter: theme === 'dark' ? 'invert(90%) hue-rotate(180deg) brightness(1.1) contrast(0.9)' : 'none' }}
                ></iframe>
                
                <svg className="absolute inset-0 w-full h-full pointer-events-none z-10 opacity-60">
                  <path d="M0,120 Q100,100 200,130 T400,110" stroke="rgba(239, 68, 68, 0.8)" strokeWidth="40" fill="none" className="animate-pulse" />
                  <rect x="150" y="80" width="100" height="80" fill="rgba(239, 68, 68, 0.4)" />
                  <text x="160" y="100" fill="white" fontSize="10" fontWeight="bold" className="uppercase">Flood Zone</text>
                  
                  <circle cx="300" cy="50" r="40" fill="rgba(16, 185, 129, 0.4)" />
                  <text x="280" y="55" fill="white" fontSize="10" fontWeight="bold" className="uppercase">Safe Zone</text>
                </svg>

                <div className="absolute bottom-4 left-4 right-4 z-20">
                   <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md p-3 rounded-xl border border-slate-200 dark:border-white/10 shadow-lg flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${latest.level === "HIGH" ? 'bg-rose-500 text-white animate-pulse' : 'bg-emerald-500 text-white'}`}>
                          <Droplets size={20} />
                        </div>
                        <div>
                          <p className="font-black text-sm text-slate-900 dark:text-white uppercase tracking-tighter">Current Risk: {latest.level === "HIGH" ? "CRITICAL" : "STABLE"}</p>
                          <p className="text-slate-600 dark:text-slate-400 text-[9px] font-bold uppercase tracking-widest">Node #001 Area Diagnostic</p>
                        </div>
                      </div>
                      <div className="hidden sm:block">
                        <div className={`px-2 py-1 rounded text-[8px] font-black uppercase tracking-widest ${latest.level === "HIGH" ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'}`}>
                          {latest.level === "HIGH" ? "EVACUATE" : "ALL CLEAR"}
                        </div>
                      </div>
                   </div>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 p-2 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-dashed border-slate-200 dark:border-slate-700">
                <div className="flex -space-x-1 shrink-0">
                  <img src={MBSP_LOGO} className="w-3 h-3 grayscale" />
                </div>
                <p className="text-[9px] text-slate-600 dark:text-slate-400 font-bold leading-tight">
                  MBSP Advisory: High flood risk areas are concentrated near the Taman Sri Rambai drainage output. Safe zones identified at higher elevations.
                </p>
              </div>
            </div>
            <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-xl">
              <h3 className="text-xl font-black mb-4 flex items-center gap-2 text-slate-900 dark:text-white uppercase tracking-tight"><AlertTriangle className="text-amber-500" /> Operational Feed</h3>
              <div className="flex flex-col gap-3 max-h-[250px] overflow-y-auto pr-2 custom-scrollbar">
                {[...data].reverse().slice(0, 10).map((log, i) => (
                  <div key={i} className={`flex items-center gap-4 p-3 rounded-xl border ${log.tof >= 1120 ? 'bg-rose-50 border-rose-200 dark:bg-rose-500/5 dark:border-rose-500/20' : 'bg-emerald-50 border-emerald-200 dark:bg-emerald-500/5 dark:border-emerald-500/20'}`}>
                    <div className={`p-2 rounded-full shrink-0 ${log.tof >= 1120 ? 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-400' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'}`}>
                      {log.tof >= 1120 ? <Trash2 size={16} /> : <CheckCircle size={16} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-center mb-1">
                        <p className={`font-black text-xs uppercase tracking-wider truncate ${log.tof >= 1120 ? 'text-rose-900 dark:text-rose-300' : 'text-emerald-900 dark:text-emerald-300'}`}>{log.trashStatus}</p>
                        <span className="text-[10px] font-mono font-bold text-slate-600 dark:text-slate-400 uppercase">{log.date}</span>
                      </div>
                      <p className="text-[10px] text-slate-700 dark:text-slate-400 font-mono font-bold uppercase truncate">Level: {log.level} | Status: {log.status}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-12 duration-1000">
          <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-2xl border border-slate-200 dark:border-white/5 rounded-3xl p-8 shadow-2xl overflow-hidden relative group">
            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
              <Activity size={120} className="text-blue-500" />
            </div>
            <div className="relative z-10 mb-8">
              <h3 className="text-2xl font-black text-slate-900 dark:text-white uppercase tracking-tighter flex items-center gap-3">
                <div className="w-1.5 h-8 bg-cyan-500 rounded-full"></div>
                Historical Depth Trend
              </h3>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 uppercase font-bold tracking-widest mt-1">
                Precision Ultrasonic Telemetry (mm) • High Resolution Chronology
              </p>
            </div>
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData.depthHistory} margin={{ top: 10, right: 30, left: 20, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#1e293b' : '#cbd5e1'} vertical={false} opacity={0.3} />
                  <XAxis dataKey="timestamp" fontSize={9} stroke={theme === 'dark' ? '#94a3b8' : '#475569'} axisLine={false} tickLine={false} minTickGap={60} tickFormatter={(t) => t.includes(':') ? t.split(' ')[1] : t}>
                    <Label value="Recording Timestamp" offset={-25} position="insideBottom" style={{ fill: theme === 'dark' ? '#94a3b8' : '#334155', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase' }} />
                  </XAxis>
                  <YAxis stroke={theme === 'dark' ? '#94a3b8' : '#475569'} fontSize={10} fontWeight="bold" axisLine={false} tickLine={false} domain={[0, 'auto']}>
                    <Label value="Water Depth (mm)" angle={-90} position="insideLeft" offset={10} style={{ fill: theme === 'dark' ? '#94a3b8' : '#334155', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase', textAnchor: 'middle' }} />
                  </YAxis>
                  <Tooltip contentStyle={{ backgroundColor: theme === 'dark' ? '#0f172a' : '#fff', borderRadius: '12px', border: '1px solid #334155', color: theme === 'dark' ? '#fff' : '#000' }} labelStyle={{ fontWeight: 'black', marginBottom: '4px', borderBottom: '1px solid #334155', paddingBottom: '4px' }} />
                  <Legend verticalAlign="top" align="right" wrapperStyle={{ paddingBottom: '20px', fontSize: '10px', fontWeight: 'black', textTransform: 'uppercase' }} />
                  <ReferenceLine y={1120} label={{ position: 'right', value: 'DANGER', fill: '#ef4444', fontSize: 10, fontWeight: 'black' }} stroke="#ef4444" strokeDasharray="5 5" />
                  <ReferenceLine y={800} label={{ position: 'right', value: 'WARNING', fill: '#f59e0b', fontSize: 10, fontWeight: 'black' }} stroke="#f59e0b" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="depth" name="Ultrasonic Depth" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }} animationDuration={1500} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-2xl border border-slate-200 dark:border-white/5 rounded-3xl overflow-hidden shadow-2xl">
            <div className="p-8 border-b border-slate-200 dark:border-white/10 flex flex-col space-y-6">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <h3 className="text-2xl font-black text-slate-900 dark:text-white uppercase tracking-tighter">Main Diagnostic Database</h3>
                  <p className="text-[10px] text-slate-500 font-bold uppercase mt-1 tracking-widest">Central Archive of Operational Integrity</p>
                </div>
                <button onClick={handleExportCSV} disabled={filteredDatabase.length === 0} className="group flex items-center gap-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white px-6 py-2.5 rounded-2xl text-[11px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-500/20 active:scale-95">
                  <FileSpreadsheet size={16} className="group-hover:rotate-12 transition-transform" />
                  Export Excel ({filteredDatabase.length} records)
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-white/5">
                <div className="space-y-1.5">
                  <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-1"><Calendar size={12} /> From Date</label>
                  <input type="date" value={filterStartDate} onChange={(e) => setFilterStartDate(e.target.value)} className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs font-bold outline-none focus:ring-2 ring-blue-500 transition-all shadow-sm" />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-1"><Calendar size={12} /> To Date</label>
                  <input type="date" value={filterEndDate} onChange={(e) => setFilterEndDate(e.target.value)} className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs font-bold outline-none focus:ring-2 ring-blue-500 transition-all shadow-sm" />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-1"><Trash2 size={12} /> Trash Status</label>
                  <select value={filterTrashStatus} onChange={(e) => setFilterTrashStatus(e.target.value)} className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs font-bold outline-none focus:ring-2 ring-blue-500 transition-all cursor-pointer shadow-sm">
                    <option value="ALL">All Status</option>
                    <option value="DETECTED">Detected</option>
                    <option value="NOT DETECTED">Not Detected</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-1"><Waves size={12} /> Water Level</label>
                  <div className="flex gap-2">
                    <select value={filterHydroLevel} onChange={(e) => setFilterHydroLevel(e.target.value)} className="flex-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs font-bold outline-none focus:ring-2 ring-blue-500 transition-all cursor-pointer shadow-sm">
                      <option value="ALL">All Levels</option>
                      <option value="LOW">Low</option>
                      <option value="NORMAL">Normal</option>
                      <option value="HIGH">High</option>
                    </select>
                    <button onClick={() => { setFilterStartDate(''); setFilterEndDate(''); setFilterTrashStatus('ALL'); setFilterHydroLevel('ALL'); }} className="p-2 rounded-xl bg-rose-500/10 text-rose-600 hover:bg-rose-500 hover:text-white transition-all border border-rose-500/20 shadow-sm"><FilterX size={18} /></button>
                  </div>
                </div>
              </div>
            </div>
            <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/95 backdrop-blur-md text-[10px] font-black text-slate-700 dark:text-slate-300 uppercase tracking-[0.2em]">
                  <tr>
                    <th className="p-6">Registration Timestamp</th>
                    <th className="p-6 text-center">ToF Reading</th>
                    <th className="p-6">Classification</th>
                    <th className="p-6 text-center">Hydro Level</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
                  {filteredDatabase.length > 0 ? (
                    filteredDatabase.map((row, i) => (
                      <tr key={i} className="hover:bg-blue-600/5 transition-colors duration-200 group">
                        <td className="p-6 font-mono font-bold text-slate-600 dark:text-slate-400 group-hover:text-blue-700 transition-colors">{row.date}</td>
                        <td className="p-6 text-center font-mono font-black text-blue-700 dark:text-blue-400">{row.tof}</td>
                        <td className="p-6">
                          <span className={`px-3 py-1.5 rounded-full font-black uppercase text-[9px] tracking-widest border ${
                            row.tof >= 1120 ? 'bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-500/20 dark:text-rose-400 dark:border-rose-500/30' : 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30'
                          }`}>{row.trashStatus}</span>
                        </td>
                        <td className="p-6 text-center"><span className={`font-black text-xs tracking-tighter ${row.level === 'HIGH' ? 'text-rose-700' : row.level === 'NORMAL' ? 'text-emerald-700' : 'text-cyan-700'}`}>{row.level}</span></td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="4" className="p-20 text-center"><div className="flex flex-col items-center gap-2 opacity-50"><Search size={48} className="text-slate-300 mb-2" /><p className="font-black uppercase tracking-widest text-slate-400">No data found</p></div></td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      <footer className="relative z-10 mt-12 py-12 border-t border-slate-200 dark:border-white/5 text-center">
        <div className="flex flex-col items-center gap-3 mb-6">
          <img src={MBSP_LOGO} className="w-10 h-auto grayscale opacity-40 hover:grayscale-0 hover:opacity-100 transition-all duration-500" />
          <p className="text-[10px] font-black text-slate-600 dark:text-slate-400 uppercase tracking-[0.4em]">MAJLIS BANDARAYA SEBERANG PERAI</p>
        </div>
        <p className="text-[10px] font-black text-slate-600 dark:text-slate-400 uppercase tracking-[0.4em]">SYSTEM CORE V3.4.5 • NEURAL ANALYTICS • {currentTime.getFullYear()}</p>
      </footer>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes blob { 0% { transform: translate(0px, 0px) scale(1); } 33% { transform: translate(30px, -50px) scale(1.1); } 66% { transform: translate(-20px, 20px) scale(0.9); } 100% { transform: translate(0px, 0px) scale(1); } }
        .animate-blob { animation: blob 7s infinite; }
        @keyframes progress-fast { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
        .animate-progress-fast { animation: progress-fast 2s linear infinite; }
        @keyframes wiggle { 0%, 100% { transform: rotate(-5deg); } 50% { transform: rotate(5deg); } }
        .animate-wiggle { animation: wiggle 0.5s ease-in-out infinite; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; } 
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(59, 130, 246, 0.2); border-radius: 10px; } 
      `}} />
    </div>
  );
};

export default App;