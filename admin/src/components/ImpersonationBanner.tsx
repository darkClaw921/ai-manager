import { Alert, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useImpersonationStore } from '@/store/impersonationStore'

export default function ImpersonationBanner() {
  const { isImpersonating, impersonatedManagerName, stopImpersonation } =
    useImpersonationStore()
  const navigate = useNavigate()

  if (!isImpersonating) {
    return null
  }

  const handleExit = () => {
    stopImpersonation()
    navigate('/managers')
  }

  return (
    <Alert
      type="warning"
      banner
      message={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>
            Вы просматриваете данные менеджера: <strong>{impersonatedManagerName}</strong>
          </span>
          <Button size="small" onClick={handleExit}>
            Выйти из режима просмотра
          </Button>
        </div>
      }
      style={{ position: 'sticky', top: 0, zIndex: 1001 }}
    />
  )
}
