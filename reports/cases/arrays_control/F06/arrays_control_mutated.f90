program arrays_control
  implicit none

  integer :: i = 0
  integer :: values(1, 1) = [1, 2, 3, 4]
  integer :: total = 0

  do i = 1, 4
     total = total + values(i)
  end do

  if (total == 10) then
     print *, total
  end if

end program arrays_control
