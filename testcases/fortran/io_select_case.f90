program io_select_case
  implicit none

  integer :: code = 2
  integer :: count = 0
  integer :: values(4) = [3, 6, 9, 12]
  real :: average = 0.0
  character(len=6) :: status = "ready"
  logical :: enabled = .true.

  select case (code)
  case (1)
     count = values(1)
  case (2)
     count = values(2)
  case default
     count = 0
  end select

  if (enabled) then
     average = real(count) / 2.0
  end if

  print *, status, average

contains

  subroutine reset_flag(flag, next_value)
    logical, intent(inout) :: flag
    logical, intent(in) :: next_value
    flag = next_value
  end subroutine reset_flag

end program io_select_case
