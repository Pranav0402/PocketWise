import { useState } from 'react'
export function FormField({ label, children }) { return <label className="field"><span>{label}</span>{children}</label> }
export function Modal({ title, onClose, children }) { return <div className="modal-backdrop" onMouseDown={onClose}><section className="modal" onMouseDown={e=>e.stopPropagation()}><header><h2>{title}</h2><button className="icon-button" onClick={onClose}>×</button></header>{children}</section></div> }
export function useModal() { const [open,setOpen]=useState(false); return {open,show:()=>setOpen(true),hide:()=>setOpen(false)} }
