import { NavLink, Outlet } from "react-router";

export function Layout() {
  const link = "px-3 py-2 text-[15px]";
  return (
    <div>
      <nav className="flex gap-1 border-b border-zinc-400 px-2">
        <NavLink to="/" className={link} end>
          Yükle
        </NavLink>
        <NavLink to="/overview" className={link}>
          Genel bakış
        </NavLink>
        <NavLink to="/transactions" className={link}>
          İşlemler
        </NavLink>
        <NavLink to="/settings" className={link}>
          Ayarlar
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
