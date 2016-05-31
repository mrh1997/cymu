int a, b = 10, c;

void demo_func()
{
	a = 3;
	if (a)
	{
		int local_var = 10;
		while (local_var -= 1)
		{
			b -= 1;
			a -= 1;
		}
	}
	else
		c = 3;
}
