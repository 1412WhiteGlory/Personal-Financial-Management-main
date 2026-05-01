import React, { useContext } from 'react'
import {UserContext} from '../../context/UserContext'
import Navbar from "./Navbar";
import SideMenu from './SideMenu';

const DashBoardLayout = ({children, activeMenu}) => {
  const { user } = useContext(UserContext)
  return (
    <div className = "">
      <Navbar activeMenu={activeMenu}></Navbar>
      {user && (
        <div className ="flex">
            {activeMenu !== "Tin tức" && (
              <div className = "max-[1024px]:hidden">
                  <SideMenu activeMenu={activeMenu}></SideMenu>
              </div>
            )}
            <div className='grow mx-5'>{children}</div>
        </div>
      )}
    </div>
  )
}

export default DashBoardLayout
